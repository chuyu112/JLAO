# JLAO Lark CLI Agent

Feishu Bot Agent with AI reply.

## Fix

Old scripts/start-bot-listener.ps1 exits immediately.
This version uses async reads and keeps stdin open.

## Files

- agent.ps1 - main event loop
- lib/logger.ps1 - logging
- lib/event-parser.ps1 - event parsing
- lib/ai-handler.ps1 - AI via bl text chat
- start-agent.ps1 - start and tail logs
- stop-agent.ps1 - stop agent

## Usage

powershell -File .\lark_CLI\start-agent.ps1   # start
powershell -File .\lark_CLI\stop-agent.ps1    # stop

Log: logs/lark-agent.log
