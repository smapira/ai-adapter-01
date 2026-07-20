# AIエージェント・スクリプトの共通管理基盤ツール

CLIで操作し、スクリプトのグループ選択とスクリプトのファイル追加、AIエージェントの設定（.github）の保存と選択、githubで管理できるツール

言語はPython。バージョンは一般的なもの


## ユースケース例
データは、ローカルの　~/.ai-adapterの中に格納する

- 会社と家で同じLLMの設定ファイルを簡単に共有したい
- 新しいパソコンを設定したので古いパソコンの設定を簡単に移行したい


## 必須要件コマンド
```
# agent management

ai_adapter.py add agent MARKDOWN_FILE_PATH
# => store a agent (ex, Reviewer, Implementer or Researcher..)

ai_adapter.py get agent XXXX
# => save a agent markdown to .github/agents/.

ai_adapter.py del agent XXXX

# environment management

ai_adapter.py add env LOCAL_PROJECT_01
# => store a environment name (ex, MyHome..)

ai_adapter.py list
# => show list all env

ai_adapter.py del env LOCAL_PROJECT_01

# script management

ai_adapter.py add bin ENVIRONMENT(optinal) SCRIPT_FILE_PATH 
# => store a SCRIPT_FILE (ex, Reviewer, Implementer or Researcher..)

ai_adapter.py get bin ENVIRONMENT(optinal) SCRIPT
# => save a agent markdown to .github/agents/.

ai_adapter.py list bin ENVIRONMENT(optinal) 
# => show specific script list

ai_adapter.py del bin ENVIRONMENT(optinal) SCRIPT

```