import openai
import numpy as np
from typing import List, Optional
from config import settings

class EmbeddingService:
    def __init__(self):
        self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = "text-embedding-3-small"
        self.embedding_dim = 1536
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        response = self.client.embeddings.create(
            model=self.model,
            input=text
        )
        
        embedding = response.data[0].embedding
        
        # Normalize the embedding vector
        embedding_array = np.array(embedding)
        normalized_embedding = embedding_array / np.linalg.norm(embedding_array)
        
        return normalized_embedding.tolist()
    
    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts in batch."""
        # OpenAI allows batch processing up to a certain limit
        max_batch_size = 100
        all_embeddings = []
        
        for i in range(0, len(texts), max_batch_size):
            batch_texts = texts[i:i + max_batch_size]
            
            response = self.client.embeddings.create(
                model=self.model,
                input=batch_texts
            )
            
            batch_embeddings = []
            for embedding_data in response.data:
                embedding = embedding_data.embedding
                
                # Normalize the embedding vector
                embedding_array = np.array(embedding)
                normalized_embedding = embedding_array / np.linalg.norm(embedding_array)
                
                batch_embeddings.append(normalized_embedding.tolist())
            
            all_embeddings.extend(batch_embeddings)
        
        return all_embeddings
    
    def compute_mean_embedding(self, embeddings: List[List[float]]) -> List[float]:
        """Compute mean-pooled embedding from a list of embeddings."""
        if not embeddings:
            raise ValueError("Cannot compute mean of empty embeddings list")
        
        # Convert to numpy array for easier computation
        embeddings_array = np.array(embeddings)
        
        # Compute mean across embeddings
        mean_embedding = np.mean(embeddings_array, axis=0)
        
        # Normalize the mean embedding
        normalized_mean = mean_embedding / np.linalg.norm(mean_embedding)
        
        return normalized_mean.tolist()

embedding_service = EmbeddingService()