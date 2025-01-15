from vectordb import PineconeManager
from embeddings import EmbeddingManager
from typing import Dict, List
import re

class ComplianceChecker:
    def __init__(self, embeddings):
        self.pinecone_manager = PineconeManager(embeddings)
        self.violation_patterns = {
            'FDCPA': {
                'harassment': {
                    'pattern': r'contact.*work|threaten|harass|abuse|repeated.*calls',
                    'severity': 'high',
                    'description': 'Potential harassment or unfair practices'
                },
                'disclosure': {
                    'pattern': r'disclose.*debt|communicate.*third.*party',
                    'severity': 'high',
                    'description': 'Unauthorized debt disclosure'
                }
            },
            'FCRA': {
                'reporting': {
                    'pattern': r'accuracy|dispute|investigation|reinvestigation',
                    'severity': 'medium',
                    'description': 'Credit reporting accuracy requirements'
                },
                'disclosure': {
                    'pattern': r'permissible.*purpose|written.*consent',
                    'severity': 'high',
                    'description': 'Credit report access requirements'
                }
            }
        }

    async def check_compliance(self, text: str) -> Dict:
        violations = []
        semantic_matches = []

        # Vector similarity search
        for regulation in self.violation_patterns.keys():
            matches = self.pinecone_manager.similarity_search(
                query=text,
                namespace=regulation,
                k=2
            )
            if matches:
                semantic_matches.extend(self._process_matches(matches, regulation))

        # Pattern-based violation detection
        detected_violations = self._detect_violations(text)
        
        return {
            'violations': detected_violations,
            'relevant_regulations': semantic_matches,
            'risk_level': self._calculate_risk_level(detected_violations)
        }

    def _detect_violations(self, text: str) -> List[Dict]:
        violations = []
        for reg_type, categories in self.violation_patterns.items():
            for category, rules in categories.items():
                if re.search(rules['pattern'], text.lower()):
                    violations.append({
                        'regulation': reg_type,
                        'category': category,
                        'severity': rules['severity'],
                        'description': rules['description']
                    })
        return violations

    def _process_matches(self, matches, regulation: str) -> List[Dict]:
        return [{
            'regulation': regulation,
            'content': match.page_content[:200],
            'source': match.metadata.get('source', ''),
            'page': match.metadata.get('page', '')
        } for match in matches]

    def _calculate_risk_level(self, violations: List[Dict]) -> str:
        if any(v['severity'] == 'high' for v in violations):
            return 'HIGH'
        elif any(v['severity'] == 'medium' for v in violations):
            return 'MEDIUM'
        return 'LOW'