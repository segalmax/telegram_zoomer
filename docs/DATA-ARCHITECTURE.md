# 💾 Data Architecture

## 🎯 Design Philosophy  
Database-first → Zero local state → Heroku-safe

## 🏗️ Core Tables (4 total)

```mermaid
erDiagram
    telegram_sessions {
        varchar session_name PK
        text session_data "gzip+base64"
        varchar environment "local|test|production"
        timestamp updated_at
    }
    
    article_chunks {
        uuid id PK
        text source_text
        text translation_text
        vector embedding "1536d OpenAI"
        varchar message_url
        timestamp created_at
    }
    
    translation_sessions {
        uuid id PK
        varchar message_id
        int total_processing_time_ms
        int memories_found
        float avg_memory_similarity
        boolean success
        timestamp session_start_time
    }
    
    memory_usage_analytics {
        uuid id PK
        uuid session_id FK
        uuid memory_pair_id FK
        float similarity_score
        float combined_score
        int rank_position
    }
```

## 📊 Table Functions

| Table | Purpose | Critical Feature |
|-------|---------|------------------|
| `telegram_sessions` | Session persistence | Compressed storage |
| `article_chunks` | Translation memory | pgvector embeddings |
| `translation_sessions` | Performance analytics | Processing metrics |
| `memory_usage_analytics` | Memory effectiveness | Similarity tracking |

## 🧠 Vector Memory System

### Storage Strategy
```python
# Store: source → translation + embedding
embedding = openai.embed(source_text)  # 1536 dimensions
save_pair(source, translation, embedding, message_url)

# Recall: semantic similarity search
memories = recall(query_text, k=10)  # Top 10 matches
```

### Vector Query Function
```sql
-- pgvector similarity search
CREATE OR REPLACE FUNCTION match_article_chunks(
  query_embedding vector(1536),
  match_count int
)
RETURNS TABLE (
  id uuid,
  source_text text,
  translation_text text,
  message_url text,
  similarity float
)
AS $$
BEGIN
  RETURN QUERY
  SELECT
    article_chunks.id,
    article_chunks.source_text,
    article_chunks.translation_text,
    article_chunks.message_url,
    (article_chunks.embedding <=> query_embedding) as similarity
  FROM article_chunks
  ORDER BY article_chunks.embedding <=> query_embedding
  LIMIT match_count;
END;
$$ LANGUAGE plpgsql;
```

## 🔄 Session Management

### Compression Strategy
```python
# Telegram session compression for storage
session_string = client.session.save()
compressed = gzip.compress(session_string.encode())
stored = base64.b64encode(compressed).decode()
```

### Environment Isolation
- **local**: Development sessions
- **production**: Live bot operations  
- **test**: Automated testing

## 📈 Analytics Architecture

### Key Metrics Tracked
```python
{
    'total_processing_time_ms': 15000,
    'memory_query_time_ms': 200,
    'memories_found': 8,
    'avg_memory_similarity': 0.75,
    'success': True
}
```

### Memory Effectiveness
- **Similarity scores**: Track semantic relevance
- **Rank positions**: Understand usage patterns
- **Combined scores**: Similarity + recency weighting

## ⚙️ Configuration
```bash
# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1...

# Vector
EMBED_MODEL=text-embedding-ada-002
TM_RECENCY_WEIGHT=0.3
```

## 🚀 Performance Optimizations

### Memory Query Efficiency
- **k=10 limit** → balance context vs speed
- **Recency weighting** → prefer recent translations
- **Similarity threshold** → filter poor matches

### Database Indexes
- **Vector index** → HNSW for fast similarity search
- **Environment index** → efficient state queries
- **Timestamp index** → analytics performance 