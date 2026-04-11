use clap::Parser;
use tokio::fs;
use tokio::io::{self, AsyncBufReadExt, BufReader};

use rag_runtime::RagRuntime;
use rag_runtime::models::UserRequest;

#[derive(Debug, Parser)]
#[command(about = "Interactive RAG runtime CLI")]
struct Cli {
    #[arg(long)]
    config: std::path::PathBuf,
    #[arg(long = "ingest-config")]
    ingest_config: std::path::PathBuf,
    #[arg(long = "questions-file")]
    questions_file: Option<std::path::PathBuf>,
    #[arg(long = "golden-retrievals-file")]
    golden_retrievals_file: Option<std::path::PathBuf>,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let cli = Cli::parse();
    let runtime = RagRuntime::from_config_paths(&cli.config, &cli.ingest_config).await?;

    if let Some(questions_path) = &cli.questions_file {
        let contents = fs::read_to_string(questions_path).await?;
        let queries = parse_batch_queries(&contents);

        let runtime = if let Some(golden_path) = &cli.golden_retrievals_file {
            runtime.with_golden_companion(golden_path, &queries).await?
        } else {
            runtime
        };

        for query in queries {
            run_query(&runtime, &query).await;
        }
        return Ok(());
    }

    let stdin = BufReader::new(io::stdin());
    let mut lines = stdin.lines();

    while let Some(line) = lines.next_line().await? {
        if line.trim() == "exit" {
            break;
        }
        run_query(&runtime, &line).await;
    }

    Ok(())
}

async fn run_query(runtime: &RagRuntime, query: &str) {
    match runtime
        .handle_request(UserRequest {
            query: query.to_string(),
        })
        .await
    {
        Ok(response) => {
            println!("{}", response.answer);
        }
        Err(error) => {
            eprintln!("{error}");
        }
    }
}

fn parse_batch_queries(contents: &str) -> Vec<String> {
    contents
        .lines()
        .map(str::trim)
        .filter(|line| !line.is_empty())
        .map(ToOwned::to_owned)
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use rag_runtime::config::{default_ingest_config_path, default_rag_runtime_config_path};

    #[test]
    fn cli_requires_explicit_paths() {
        let result = Cli::try_parse_from(["rag_runtime"]);
        assert!(result.is_err());
        assert!(
            default_rag_runtime_config_path().ends_with("Execution/rag_runtime/rag_runtime.toml")
        );
        assert!(default_ingest_config_path().ends_with("Execution/ingest/dense/ingest.toml"));
    }

    #[test]
    fn cli_accepts_optional_questions_file() {
        let result = Cli::try_parse_from([
            "rag_runtime",
            "--config",
            "runtime.toml",
            "--ingest-config",
            "ingest.toml",
            "--questions-file",
            "questions.txt",
        ])
        .unwrap();
        assert_eq!(
            result.questions_file.unwrap(),
            std::path::PathBuf::from("questions.txt")
        );
    }

    #[test]
    fn batch_query_parser_skips_blank_lines() {
        let queries = parse_batch_queries("one\n\n two \n\nthree\n");
        assert_eq!(queries, vec!["one", "two", "three"]);
    }
}
