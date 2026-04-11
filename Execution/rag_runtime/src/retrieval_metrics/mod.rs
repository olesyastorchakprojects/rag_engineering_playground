use std::collections::{HashMap, HashSet};

use thiserror::Error;

use crate::models::{GoldenRetrievalTargets, RetrievalQualityMetrics};

// Valid graded relevance scores per the current contract.
const VALID_GRADES: &[f32] = &[0.0, 0.5, 1.0];

#[derive(Debug, Error)]
pub enum RetrievalMetricsError {
    #[error("invalid golden retrieval targets for metric computation: {message}")]
    InvalidGoldenTargets { message: String },
    #[error("invalid effective top-k for metric computation: k must be >= 1")]
    InvalidTopK,
    #[error("inconsistent graded relevance state: {message}")]
    InconsistentGradedRelevance { message: String },
    #[error("unexpected internal metric computation state: {message}")]
    UnexpectedState { message: String },
}

pub struct RetrievalMetricsHelper;

impl RetrievalMetricsHelper {
    /// Compute per-request retrieval quality metrics.
    ///
    /// `ranked_chunk_ids` is the full ordered output of the current stage (chunk_id strings
    /// in stage output rank order). `k` is the effective top-k cutoff.
    pub fn compute(
        golden: &GoldenRetrievalTargets,
        ranked_chunk_ids: &[String],
        k: usize,
    ) -> Result<RetrievalQualityMetrics, RetrievalMetricsError> {
        if k == 0 {
            return Err(RetrievalMetricsError::InvalidTopK);
        }

        // Build string sets from UUID lists for comparison.
        let soft_set: HashSet<String> = golden
            .soft_positive_chunk_ids
            .iter()
            .map(|u| u.to_string())
            .collect();
        let strict_set: HashSet<String> = golden
            .strict_positive_chunk_ids
            .iter()
            .map(|u| u.to_string())
            .collect();

        if soft_set.is_empty() {
            return Err(RetrievalMetricsError::InvalidGoldenTargets {
                message: "soft_positive_chunk_ids must be non-empty".to_string(),
            });
        }
        if strict_set.is_empty() {
            return Err(RetrievalMetricsError::InvalidGoldenTargets {
                message: "strict_positive_chunk_ids must be non-empty".to_string(),
            });
        }
        for id in &strict_set {
            if !soft_set.contains(id) {
                return Err(RetrievalMetricsError::InvalidGoldenTargets {
                    message: format!(
                        "strict_positive_chunk_ids is not a subset of soft_positive_chunk_ids: \
                         chunk_id {} is missing from soft",
                        id
                    ),
                });
            }
        }

        // Build and validate graded relevance map.
        let mut grade_map: HashMap<String, f32> = HashMap::new();
        for item in &golden.graded_relevance {
            let score = item.score;
            if !VALID_GRADES.iter().any(|&v| (v - score).abs() < 1e-6) {
                return Err(RetrievalMetricsError::InconsistentGradedRelevance {
                    message: format!(
                        "unsupported graded relevance score {} for chunk_id {}; \
                         valid values are 0.0, 0.5, 1.0",
                        score, item.chunk_id
                    ),
                });
            }
            grade_map.insert(item.chunk_id.to_string(), score);
        }

        for id in &soft_set {
            if !grade_map.contains_key(id) {
                return Err(RetrievalMetricsError::InvalidGoldenTargets {
                    message: format!(
                        "soft_positive_chunk_id {} is missing from graded_relevance",
                        id
                    ),
                });
            }
        }
        for id in &strict_set {
            if !grade_map.contains_key(id) {
                return Err(RetrievalMetricsError::InvalidGoldenTargets {
                    message: format!(
                        "strict_positive_chunk_id {} is missing from graded_relevance",
                        id
                    ),
                });
            }
        }

        // Build ActualTopK_dedup: first k unique chunk ids in rank order.
        let top_k_dedup = Self::build_top_k_dedup(ranked_chunk_ids, k);

        let recall_soft = Self::compute_recall(&top_k_dedup, &soft_set, soft_set.len());
        let recall_strict = Self::compute_recall(&top_k_dedup, &strict_set, strict_set.len());

        let (rr_soft, first_relevant_rank_soft) = Self::compute_rr(&top_k_dedup, &soft_set);
        let (rr_strict, first_relevant_rank_strict) = Self::compute_rr(&top_k_dedup, &strict_set);

        let num_relevant_soft = Self::compute_relevant_count(&top_k_dedup, &soft_set);
        let num_relevant_strict = Self::compute_relevant_count(&top_k_dedup, &strict_set);

        let ndcg = Self::compute_ndcg(&top_k_dedup, &grade_map, k);

        Ok(RetrievalQualityMetrics {
            evaluated_k: k,
            recall_soft,
            recall_strict,
            rr_soft,
            rr_strict,
            ndcg,
            first_relevant_rank_soft,
            first_relevant_rank_strict,
            num_relevant_soft,
            num_relevant_strict,
        })
    }

    fn build_top_k_dedup(ranked_chunk_ids: &[String], k: usize) -> Vec<String> {
        let mut seen: HashSet<&str> = HashSet::new();
        let mut result: Vec<String> = Vec::with_capacity(k);
        for id in ranked_chunk_ids {
            if result.len() >= k {
                break;
            }
            if seen.insert(id.as_str()) {
                result.push(id.clone());
            }
        }
        result
    }

    fn compute_recall(top_k_dedup: &[String], rel_set: &HashSet<String>, rel_count: usize) -> f32 {
        if rel_count == 0 {
            return 0.0;
        }
        let hits = top_k_dedup
            .iter()
            .filter(|id| rel_set.contains(*id))
            .count();
        hits as f32 / rel_count as f32
    }

    fn compute_rr(top_k_dedup: &[String], rel_set: &HashSet<String>) -> (f32, Option<usize>) {
        for (i, id) in top_k_dedup.iter().enumerate() {
            if rel_set.contains(id) {
                let rank = i + 1; // 1-based
                return (1.0 / rank as f32, Some(rank));
            }
        }
        (0.0, None)
    }

    fn compute_relevant_count(top_k_dedup: &[String], rel_set: &HashSet<String>) -> usize {
        top_k_dedup
            .iter()
            .filter(|id| rel_set.contains(*id))
            .count()
    }

    fn compute_ndcg(top_k_dedup: &[String], grade_map: &HashMap<String, f32>, k: usize) -> f32 {
        let dcg = Self::compute_dcg(
            top_k_dedup
                .iter()
                .map(|id| *grade_map.get(id.as_str()).unwrap_or(&0.0)),
        );

        // Build ideal ranking: all grades sorted desc, ties broken by chunk_id asc for
        // determinism, take up to k.
        let mut grade_pairs: Vec<(f32, &str)> = grade_map
            .iter()
            .map(|(id, &score)| (score, id.as_str()))
            .collect();
        grade_pairs.sort_by(|a, b| {
            b.0.partial_cmp(&a.0)
                .unwrap_or(std::cmp::Ordering::Equal)
                .then_with(|| a.1.cmp(b.1))
        });

        let ideal_grades = grade_pairs.into_iter().take(k).map(|(g, _)| g);
        let idcg = Self::compute_dcg(ideal_grades);

        if idcg <= 0.0 {
            return 0.0;
        }
        dcg / idcg
    }

    // DCG formula: sum of rel_i / log2(rank + 1) where rank is 1-based.
    // With 0-based iterator index i: rank = i+1, denominator = log2(i+2).
    fn compute_dcg(grades: impl Iterator<Item = f32>) -> f32 {
        grades
            .enumerate()
            .map(|(i, rel)| rel / (i as f32 + 2.0).log2())
            .sum()
    }
}

#[cfg(test)]
mod tests {
    use uuid::Uuid;

    use super::*;
    use crate::models::GradedChunkRelevance;

    fn uuid_str(s: &str) -> String {
        // Use a deterministic UUID v5 from a name so tests are readable.
        Uuid::new_v5(&Uuid::NAMESPACE_OID, s.as_bytes()).to_string()
    }

    fn make_golden(
        soft: &[&str],
        strict: &[&str],
        grades: &[(&str, f32)],
    ) -> GoldenRetrievalTargets {
        GoldenRetrievalTargets {
            soft_positive_chunk_ids: soft
                .iter()
                .map(|s| Uuid::new_v5(&Uuid::NAMESPACE_OID, s.as_bytes()))
                .collect(),
            strict_positive_chunk_ids: strict
                .iter()
                .map(|s| Uuid::new_v5(&Uuid::NAMESPACE_OID, s.as_bytes()))
                .collect(),
            graded_relevance: grades
                .iter()
                .map(|(s, score)| GradedChunkRelevance {
                    chunk_id: Uuid::new_v5(&Uuid::NAMESPACE_OID, s.as_bytes()),
                    score: *score,
                })
                .collect(),
        }
    }

    fn ids(names: &[&str]) -> Vec<String> {
        names.iter().map(|s| uuid_str(s)).collect()
    }

    // 4.2r — recall uses ActualTopK_dedup not raw duplicated list.
    #[test]
    fn recall_uses_deduplicated_top_k() {
        let golden = make_golden(&["a", "b"], &["a"], &[("a", 1.0), ("b", 0.5)]);
        // ranked list: a, a, b — after dedup top-3: [a, b]. Both soft targets hit → recall=1.0.
        // Without dedup, rank-3 would be 'b' but 'a' would be counted twice.
        let ranked = ids(&["a", "a", "b"]);
        let result = RetrievalMetricsHelper::compute(&golden, &ranked, 3).unwrap();
        assert_eq!(result.recall_soft, 1.0);
        assert_eq!(result.num_relevant_soft, 2);
    }

    // 4.2r — rr_at_k_soft returns 1/rank of first soft-relevant chunk in ActualTopK_dedup.
    #[test]
    fn rr_soft_returns_reciprocal_of_first_soft_relevant_rank() {
        let golden = make_golden(&["b"], &["b"], &[("b", 1.0)]);
        // ranked: [irrelevant, b] — first soft hit at rank 2.
        let ranked = ids(&["irrelevant", "b"]);
        let golden_with_irrelevant = GoldenRetrievalTargets {
            soft_positive_chunk_ids: golden.soft_positive_chunk_ids,
            strict_positive_chunk_ids: golden.strict_positive_chunk_ids,
            graded_relevance: golden.graded_relevance,
        };
        let result = RetrievalMetricsHelper::compute(&golden_with_irrelevant, &ranked, 2).unwrap();
        let expected_rr = 1.0 / 2.0_f32;
        assert!((result.rr_soft - expected_rr).abs() < 1e-6);
        assert_eq!(result.first_relevant_rank_soft, Some(2));
    }

    // 4.2r — rr_at_k_strict returns 0 when no strict-relevant chunk in ActualTopK_dedup.
    #[test]
    fn rr_strict_is_zero_when_no_strict_relevant_in_top_k() {
        // soft has "a", strict has "b", but "b" is not in ranked list.
        let golden = make_golden(&["a", "b"], &["b"], &[("a", 0.5), ("b", 1.0)]);
        let ranked = ids(&["a"]); // only soft hit, no strict hit
        let result = RetrievalMetricsHelper::compute(&golden, &ranked, 2).unwrap();
        assert_eq!(result.rr_strict, 0.0);
        assert_eq!(result.first_relevant_rank_strict, None);
    }

    // 4.2r — first_relevant_rank_soft/strict are None when no matching relevant chunk exists.
    #[test]
    fn first_relevant_rank_is_none_when_no_hit() {
        let golden = make_golden(&["a", "b"], &["a"], &[("a", 1.0), ("b", 0.5)]);
        let ranked = ids(&["irrelevant"]); // no relevant chunk in ranked
        let result = RetrievalMetricsHelper::compute(&golden, &ranked, 1).unwrap();
        assert_eq!(result.first_relevant_rank_soft, None);
        assert_eq!(result.first_relevant_rank_strict, None);
        assert_eq!(result.rr_soft, 0.0);
        assert_eq!(result.rr_strict, 0.0);
    }

    // 4.2r — num_relevant_soft and num_relevant_strict count unique relevant chunk ids.
    #[test]
    fn num_relevant_counts_unique_relevant_in_top_k_dedup() {
        let golden = make_golden(
            &["a", "b", "c"],
            &["a"],
            &[("a", 1.0), ("b", 0.5), ("c", 0.5)],
        );
        let ranked = ids(&["a", "b", "irrelevant"]);
        let result = RetrievalMetricsHelper::compute(&golden, &ranked, 3).unwrap();
        assert_eq!(result.num_relevant_soft, 2); // a and b
        assert_eq!(result.num_relevant_strict, 1); // only a
    }

    // 4.2r — ndcg uses deduplicated ranking and ideal ranking from graded_relevance.
    #[test]
    fn ndcg_uses_deduplicated_actual_and_ideal_ranking() {
        let golden = make_golden(&["a", "b"], &["a"], &[("a", 1.0), ("b", 0.5)]);
        // Perfect order [a, b] should give ndcg = 1.0.
        let ranked = ids(&["a", "b"]);
        let result = RetrievalMetricsHelper::compute(&golden, &ranked, 2).unwrap();
        assert!(
            (result.ndcg - 1.0).abs() < 1e-5,
            "expected ndcg=1.0, got {}",
            result.ndcg
        );

        // Swapped order [b, a] should give ndcg < 1.0.
        let ranked_swapped = ids(&["b", "a"]);
        let result_swapped = RetrievalMetricsHelper::compute(&golden, &ranked_swapped, 2).unwrap();
        assert!(
            result_swapped.ndcg < 1.0,
            "expected ndcg<1.0 for swapped order"
        );
    }

    // 4.2r — duplicate chunk ids don't increase recall/rr/counts/nDCG after first occurrence.
    #[test]
    fn duplicates_do_not_increase_metrics_after_first_occurrence() {
        let golden = make_golden(&["a"], &["a"], &[("a", 1.0)]);
        // ranked: [a, a, a] — after dedup top-3: [a]. recall = 1/1 = 1.0, not 3.0.
        let ranked = ids(&["a", "a", "a"]);
        let result = RetrievalMetricsHelper::compute(&golden, &ranked, 3).unwrap();
        assert_eq!(result.recall_soft, 1.0);
        assert_eq!(result.num_relevant_soft, 1);
        assert_eq!(result.first_relevant_rank_soft, Some(1));

        // Without dedup, rr could incorrectly count 3 hits.
        // ndcg: dcg = 1.0/log2(2) = 1.0; idcg = same → ndcg = 1.0.
        assert!((result.ndcg - 1.0).abs() < 1e-5);
    }

    // 4.2r — rejects empty soft_positive_chunk_ids.
    #[test]
    fn rejects_empty_soft_positive_chunk_ids() {
        let golden = GoldenRetrievalTargets {
            soft_positive_chunk_ids: vec![],
            strict_positive_chunk_ids: vec![Uuid::new_v5(&Uuid::NAMESPACE_OID, b"a")],
            graded_relevance: vec![GradedChunkRelevance {
                chunk_id: Uuid::new_v5(&Uuid::NAMESPACE_OID, b"a"),
                score: 1.0,
            }],
        };
        let err = RetrievalMetricsHelper::compute(&golden, &[], 3).unwrap_err();
        assert!(matches!(
            err,
            RetrievalMetricsError::InvalidGoldenTargets { .. }
        ));
    }

    // 4.2r — rejects empty strict_positive_chunk_ids.
    #[test]
    fn rejects_empty_strict_positive_chunk_ids() {
        let golden = GoldenRetrievalTargets {
            soft_positive_chunk_ids: vec![Uuid::new_v5(&Uuid::NAMESPACE_OID, b"a")],
            strict_positive_chunk_ids: vec![],
            graded_relevance: vec![GradedChunkRelevance {
                chunk_id: Uuid::new_v5(&Uuid::NAMESPACE_OID, b"a"),
                score: 1.0,
            }],
        };
        let err = RetrievalMetricsHelper::compute(&golden, &[], 3).unwrap_err();
        assert!(matches!(
            err,
            RetrievalMetricsError::InvalidGoldenTargets { .. }
        ));
    }

    // 4.2r — rejects strict not subset of soft.
    #[test]
    fn rejects_strict_not_subset_of_soft() {
        // strict has "b" which is not in soft.
        let golden = make_golden(&["a"], &["b"], &[("a", 1.0), ("b", 1.0)]);
        let err = RetrievalMetricsHelper::compute(&golden, &ids(&["a"]), 1).unwrap_err();
        assert!(matches!(
            err,
            RetrievalMetricsError::InvalidGoldenTargets { .. }
        ));
    }

    // 4.2r — rejects soft/strict chunk id missing from graded_relevance.
    #[test]
    fn rejects_soft_chunk_id_missing_from_graded_relevance() {
        let golden = GoldenRetrievalTargets {
            soft_positive_chunk_ids: vec![
                Uuid::new_v5(&Uuid::NAMESPACE_OID, b"a"),
                Uuid::new_v5(&Uuid::NAMESPACE_OID, b"b"),
            ],
            strict_positive_chunk_ids: vec![Uuid::new_v5(&Uuid::NAMESPACE_OID, b"a")],
            graded_relevance: vec![
                // "b" is missing from graded_relevance
                GradedChunkRelevance {
                    chunk_id: Uuid::new_v5(&Uuid::NAMESPACE_OID, b"a"),
                    score: 1.0,
                },
            ],
        };
        let err = RetrievalMetricsHelper::compute(&golden, &[], 3).unwrap_err();
        assert!(matches!(
            err,
            RetrievalMetricsError::InvalidGoldenTargets { .. }
        ));
    }

    // 4.2r — rejects unsupported graded_relevance score values.
    #[test]
    fn rejects_unsupported_graded_relevance_score() {
        let golden = GoldenRetrievalTargets {
            soft_positive_chunk_ids: vec![Uuid::new_v5(&Uuid::NAMESPACE_OID, b"a")],
            strict_positive_chunk_ids: vec![Uuid::new_v5(&Uuid::NAMESPACE_OID, b"a")],
            graded_relevance: vec![GradedChunkRelevance {
                chunk_id: Uuid::new_v5(&Uuid::NAMESPACE_OID, b"a"),
                score: 0.75, // not in {0.0, 0.5, 1.0}
            }],
        };
        let err = RetrievalMetricsHelper::compute(&golden, &[], 3).unwrap_err();
        assert!(matches!(
            err,
            RetrievalMetricsError::InconsistentGradedRelevance { .. }
        ));
    }
}
