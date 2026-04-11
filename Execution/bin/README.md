# Execution Bin

This directory contains thin launchers only.

Current entrypoints:

- `run_stack.py`
  - master launcher for `rag-runtime` and `eval-engine`
- `eval_fixed`
  - shortcut for `run_stack.py eval-engine --scenario fixed`
- `eval_struct`
  - shortcut for `run_stack.py eval-engine --scenario structural`

## Optional Shell Completion

`run_stack.py` is compatible with `argcomplete`.

Typical one-time setup for Bash:

```bash
pip install argcomplete
activate-global-python-argcomplete --user
eval "$(register-python-argcomplete /home/olesia/code/prompt_gen_proj/Execution/bin/run_stack.py)"
```

If you do not want global completion, registering only this script is enough.

## Suggested Shell Aliases

```bash
alias eval-fixed='/home/olesia/code/prompt_gen_proj/Execution/bin/eval_fixed'
alias eval-struct='/home/olesia/code/prompt_gen_proj/Execution/bin/eval_struct'

alias rag-fixed-noreranker='/home/olesia/code/prompt_gen_proj/Execution/bin/run_stack.py rag-runtime --scenario fixed-pass-through'
alias rag-fixed-heuristic='/home/olesia/code/prompt_gen_proj/Execution/bin/run_stack.py rag-runtime --scenario fixed-heuristic'
alias rag-fixed-cross-encoder='/home/olesia/code/prompt_gen_proj/Execution/bin/run_stack.py rag-runtime --scenario fixed-cross-encoder'

alias rag-struct-noreranker='/home/olesia/code/prompt_gen_proj/Execution/bin/run_stack.py rag-runtime --scenario structural-pass-through'
alias rag-struct-heuristic='/home/olesia/code/prompt_gen_proj/Execution/bin/run_stack.py rag-runtime --scenario structural-heuristic'
alias rag-struct-cross-encoder='/home/olesia/code/prompt_gen_proj/Execution/bin/run_stack.py rag-runtime --scenario structural-cross-encoder'
```
