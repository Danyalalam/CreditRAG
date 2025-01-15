from compliance_checker import ComplianceChecker
from embeddings import EmbeddingManager
import asyncio
from dotenv import load_dotenv
import json

load_dotenv()

async def test_compliance():
    embedding_manager = EmbeddingManager()
    checker = ComplianceChecker(embedding_manager.embeddings)
    
    test_cases = [
        "We will continue to call your workplace until you pay",
        "Your credit report will be marked as delinquent for 7 years",
        "We've shared your debt information with your employer"
    ]
    
    for text in test_cases:
        print(f"\nAnalyzing text: {text}")
        results = await checker.check_compliance(text)
        print(json.dumps(results, indent=2))

if __name__ == "__main__":
    asyncio.run(test_compliance())