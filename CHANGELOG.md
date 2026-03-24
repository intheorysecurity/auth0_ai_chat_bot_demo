# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- **OpenAI provider:** Function/tool `parameters` JSON Schemas are normalized so every `type: "object"` includes a `properties` object (empty `{}` when there are no arguments). This avoids OpenAI API `400` errors such as `invalid_function_parameters` / “object schema missing properties” for built-in tools like `whoami`, `list_orders`, and `list_products`, and for MCP tools with the same pattern ([`backend/app/llm/openai_provider.py`](backend/app/llm/openai_provider.py)).

## [Earlier]

Prior work (Auth0, FGA, CIBA deferred checkout, Ollama tool IDs, FGA write body without empty `deletes`, docs, and initial GitHub publish) predates this changelog file.
