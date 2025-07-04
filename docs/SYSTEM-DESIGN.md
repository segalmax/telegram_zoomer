# 🏗️ System Design

## 🎯 What It Does
Telegram bot that translates news posts → Russian zoomer slang → publishes with semantic context links

## 🧠 Core Principles
- **Event-Driven**: Real-time message processing (no polling)
- **AI-Enhanced**: Claude Sonnet 4 with translation memory
- **Database-First**: All state in Supabase (Heroku-safe)
- **Stateless**: Survives dyno restarts

## 🏗️ Architecture

```mermaid
graph TB
    TG[Telegram API] --> BOT[Event Handler]
    BOT --> EXTRACT[Article Extractor]
    BOT --> MEMORY[Vector Memory]
    BOT --> TRANS[Translator]
    
    TRANS --> CLAUDE[Claude Sonnet 4]
    MEMORY --> DB[(Supabase)]
    EXTRACT --> NEWS[News Sites]
    
    BOT --> DST[Destination Channel]
    
    subgraph "Core Tables"
        DB --> T1[article_chunks]
        DB --> T2[translation_sessions] 
        DB --> T3[memory_usage_analytics]
        DB --> T4[telegram_sessions]
    end
```

## 🔄 Main Flow (30 seconds)
1. **Telegram event** → New message detected
2. **Extract content** → Full article if URL present  
3. **Query memory** → Find similar translations (k=10, semantic)
4. **Translate + link** → Claude with memory context  
5. **Post result** → With embedded semantic links
6. **Store memory** → Save for future context

## 🎛️ Core Components
| Component | Purpose | Key File |
|-----------|---------|----------|
| **Event Handler** | Message processing | `app/bot.py` |
| **Translator** | AI + linking | `app/translator.py` |
| **Vector Memory** | Translation memory | `app/vector_store.py` |
| **Session Manager** | Persistence | `app/session_manager.py` |

## 📊 Data Flow

```mermaid
sequenceDiagram
    Telegram->>Bot: New message
    Bot->>VectorStore: Query memory (k=10)
    VectorStore-->>Bot: Similar translations
    Bot->>Translator: Translate with context
    Translator->>Claude: API call
    Claude-->>Translator: Translation + links
    Bot->>Telegram: Post translation
    Bot->>VectorStore: Save new memory
```

## 🎯 Performance
- **Translation**: <30s
- **Memory recall**: <1s  
- **Success rate**: >95%
- **Tests**: 6 pass, 0 skip 