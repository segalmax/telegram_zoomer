# Telegram NYT-to-Zoomer Bot - Project Tasks

## MVP Core Functionality
- [x] Basic bot script (`bot.py`)
- [x] Telegram client connection and authentication
- [x] Listen to `SRC_CHANNEL` for new messages
- [x] Extract text from messages
- [x] Basic error handling and logging

## Translation Module (`translator.py`)
- [x] Connect to OpenAI API
- [x] Implement translation function for "left" style
- [x] Implement translation function for "right" style
- [x] Allow selection of translation style (`TRANSLATION_STYLE` env var: `left`, `right`, `both`)
- [x] Add source attribution (original NYT link) to translations

## Image Generation Module (`image_generator.py`)
- [x] Connect to OpenAI API (DALL-E)
- [x] Generate image based on post content
- [x] Option to disable image generation (`GENERATE_IMAGES` env var)
- [x] Integrate with Stability AI as an alternative
    - [x] Add `USE_STABILITY_AI` env var
    - [ ] Optimize Stability AI prompts/settings for better consistency

## Posting to Destination
- [x] Post translated text to `DST_CHANNEL`
- [x] Post generated image along with translation
    - [x] Handle image as file upload
    - [x] Handle image as URL
- [x] Correctly format posts for "both" styles (Left header, image, Left text, Right header, Right text)
- [x] Handle Telegram message length limits (e.g., for captions)

## Batch Processing
- [x] Implement CLI argument `--process-recent N` to fetch and translate N last posts
- [x] Add timeouts and error handling for batch processing

## Reliability & Maintainability
- [x] Robust error handling throughout the application
- [x] Clear logging for diagnostics
- [x] Fix "database is locked" SQLite error (session file access)
- [x] Implement a keep-alive/ping mechanism for the Telegram connection
- [x] Multiple strategies for handling missed events:
    - [x] Periodic client.catch_up() calls to force update retrieval
    - [x] Manual channel polling with GetChannelDifferenceRequest for large channels
    - [x] Background tasks to check for new messages if events are missed
    - [x] Use UpdateStatusRequest to keep connections alive and receiving updates
- [x] Implement persistent session handling to avoid frequent re-authentication
- [x] Comprehensive end-to-end automated testing
- [x] Code cleanup and organization (ongoing)

## Configuration
- [x] Use `.env` file for all configurations
- [x] Document all required environment variables in `README.md`

## Deployment & Operations (Simplified for MVP tracking)
- [x] Basic `README.md` with setup and run instructions (reviewed/updated)

## Future Ideas / Nice-to-Haves (Backlog)
- [ ] More sophisticated image generation prompts:
    - [ ] Caricature/cartoon style for humor
    - [ ] Meme-like or infographic style
    - [ ] Ensure consistent visual style for images
- [ ] User command to trigger translation of a specific URL
- [ ] Interactive setup/auth script (was `scripts/complete_auth.py`)
- [ ] More advanced error recovery (e.g., retry mechanisms with backoff for API calls)
- [ ] Dashboard/UI to monitor bot activity and stats
- [ ] Support for other source news channels
- [ ] Store processed message IDs to avoid re-processing after restarts (if not already handled by fetching only new ones)
- [ ] Improve logging structure (e.g., JSON logs, more context)
- [ ] CI/CD pipeline for automated testing and deployment
- [ ] Add more unit and integration tests 