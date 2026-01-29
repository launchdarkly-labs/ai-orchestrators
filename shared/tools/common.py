"""
Common tools that work across all orchestration frameworks.

These are framework-agnostic tool definitions. Each framework
applies its own decorator when importing these tools.
"""

import re
import json
from typing import List, Dict, Any


def letter_counter(word: str, letter: str) -> int:
    """
    Count occurrences of a specific letter in a word.

    Args:
        word (str): The input word to search in
        letter (str): The specific letter to count

    Returns:
        int: The number of occurrences of the letter in the word
    """
    if not isinstance(word, str) or not isinstance(letter, str):
        return 0

    if len(letter) != 1:
        raise ValueError("The 'letter' parameter must be a single character")

    return word.lower().count(letter.lower())


def word_counter(text: str) -> dict:
    """
    Count words in a text string.

    Args:
        text (str): The input text to analyze

    Returns:
        dict: Dictionary with word counts and statistics
    """
    if not isinstance(text, str):
        return {"word_count": 0, "character_count": 0, "unique_words": 0}

    words = text.split()
    unique_words = len(set(words))

    return {
        "word_count": len(words),
        "character_count": len(text),
        "unique_words": unique_words,
        "average_word_length": sum(len(word) for word in words) / len(words) if words else 0
    }


# Medical Diagnosis Tools

def text_parser(medical_case: str) -> dict:
    """
    Extract structured information from medical case text.
    
    Args:
        medical_case (str): Raw medical case text to parse
        
    Returns:
        dict: Structured medical information
    """
    if not isinstance(medical_case, str):
        return {"error": "Invalid input: medical_case must be a string"}
    
    # Extract key information using regex patterns
    result = {
        "demographics": {},
        "chief_complaint": "",
        "symptoms": [],
        "medical_history": [],
        "medications": [],
        "family_history": []
    }
    
    # Extract age
    age_match = re.search(r'(\d+)[-\s]?year[-\s]?old', medical_case, re.IGNORECASE)
    if age_match:
        result["demographics"]["age"] = int(age_match.group(1))
    
    # Extract gender
    gender_match = re.search(r'\b(male|female|man|woman)\b', medical_case, re.IGNORECASE)
    if gender_match:
        result["demographics"]["gender"] = gender_match.group(1).lower()
    
    # Extract chief complaint (usually first sentence or after "presents with")
    complaint_match = re.search(r'presents with (.+?)(?:\.|,|for)', medical_case, re.IGNORECASE)
    if complaint_match:
        result["chief_complaint"] = complaint_match.group(1).strip()
    
    return result


def symptom_extractor(case_text: str) -> list:
    """
    Extract and categorize symptoms from case description.
    
    Args:
        case_text (str): Medical case text containing symptoms
        
    Returns:
        list: List of extracted symptoms with categories
    """
    if not isinstance(case_text, str):
        return []
    
    # Common medical symptoms to look for
    symptom_patterns = {
        "pain": r'\b(pain|ache|aching|hurt|hurting|sore)\b',
        "breathing": r'\b(shortness of breath|dyspnea|breathless|wheezing)\b',
        "cardiac": r'\b(chest pain|palpitations|heart racing|irregular heartbeat)\b',
        "neurological": r'\b(headache|dizziness|confusion|weakness|numbness)\b',
        "gastrointestinal": r'\b(nausea|vomiting|diarrhea|constipation|abdominal pain)\b',
        "constitutional": r'\b(fever|fatigue|weight loss|night sweats|chills)\b'
    }
    
    symptoms = []
    for category, pattern in symptom_patterns.items():
        matches = re.findall(pattern, case_text, re.IGNORECASE)
        for match in matches:
            symptoms.append({
                "symptom": match,
                "category": category
            })
    
    return symptoms


def differential_generator(symptoms: list) -> list:
    """
    Generate differential diagnosis list based on symptoms.
    
    Args:
        symptoms (list): List of symptoms to analyze
        
    Returns:
        list: List of possible diagnoses
    """
    if not isinstance(symptoms, list):
        return []
    
    # Simple symptom-to-diagnosis mapping for demonstration
    # In a real system, this would use a medical knowledge base
    diagnosis_mapping = {
        "chest pain": ["Myocardial infarction", "Angina", "Pulmonary embolism", "Aortic dissection", "Pneumonia"],
        "shortness of breath": ["Heart failure", "Asthma", "COPD", "Pneumonia", "Pulmonary embolism"],
        "headache": ["Tension headache", "Migraine", "Cluster headache", "Hypertension", "Meningitis"],
        "abdominal pain": ["Appendicitis", "Gallbladder disease", "Peptic ulcer", "Pancreatitis", "Bowel obstruction"]
    }
    
    differential = set()
    
    # Extract symptom text from symptom objects
    symptom_texts = []
    for symptom in symptoms:
        if isinstance(symptom, dict):
            symptom_texts.append(symptom.get("symptom", ""))
        else:
            symptom_texts.append(str(symptom))
    
    # Match symptoms to diagnoses
    for symptom_text in symptom_texts:
        for key_symptom, diagnoses in diagnosis_mapping.items():
            if key_symptom.lower() in symptom_text.lower():
                differential.update(diagnoses)
    
    return list(differential)


def medical_database_search(condition: str) -> dict:
    """
    Search medical knowledge base for condition information.
    
    Args:
        condition (str): Medical condition to search for
        
    Returns:
        dict: Information about the condition
    """
    if not isinstance(condition, str):
        return {"error": "Invalid input: condition must be a string"}
    
    # Simplified medical knowledge base
    medical_db = {
        "myocardial infarction": {
            "prevalence": "High in older adults with risk factors",
            "typical_presentation": "Chest pain, shortness of breath, sweating, nausea",
            "diagnostic_criteria": "ECG changes, elevated troponins, clinical presentation",
            "risk_factors": "Age, smoking, hypertension, diabetes, family history"
        },
        "angina": {
            "prevalence": "Common in coronary artery disease",
            "typical_presentation": "Chest pain with exertion, relieved by rest",
            "diagnostic_criteria": "Exercise stress test, coronary angiography",
            "risk_factors": "Similar to MI but less acute"
        },
        "pneumonia": {
            "prevalence": "Common respiratory infection",
            "typical_presentation": "Cough, fever, shortness of breath, chest pain",
            "diagnostic_criteria": "Chest X-ray, clinical symptoms, lab findings",
            "risk_factors": "Age, immunocompromised, chronic diseases"
        }
    }
    
    condition_lower = condition.lower()
    for key, info in medical_db.items():
        if key in condition_lower or condition_lower in key:
            return {
                "condition": condition,
                "found": True,
                **info
            }
    
    return {
        "condition": condition,
        "found": False,
        "message": "Condition not found in knowledge base"
    }


def diagnostic_criteria_checker(symptoms: list, condition: str) -> dict:
    """
    Check if symptoms match diagnostic criteria for condition.
    
    Args:
        symptoms (list): List of patient symptoms
        condition (str): Medical condition to check against
        
    Returns:
        dict: Match analysis with percentage and details
    """
    if not isinstance(symptoms, list) or not isinstance(condition, str):
        return {"error": "Invalid input types"}
    
    # Get condition info
    condition_info = medical_database_search(condition)
    if not condition_info.get("found"):
        return {"match_percentage": 0, "reason": "Condition not in knowledge base"}
    
    typical_symptoms = condition_info.get("typical_presentation", "").lower().split(", ")
    
    # Count matching symptoms
    matches = 0
    total_criteria = len(typical_symptoms)
    
    symptom_texts = []
    for symptom in symptoms:
        if isinstance(symptom, dict):
            symptom_texts.append(symptom.get("symptom", "").lower())
        else:
            symptom_texts.append(str(symptom).lower())
    
    for typical_symptom in typical_symptoms:
        for patient_symptom in symptom_texts:
            if typical_symptom in patient_symptom or patient_symptom in typical_symptom:
                matches += 1
                break
    
    match_percentage = (matches / total_criteria * 100) if total_criteria > 0 else 0
    
    return {
        "condition": condition,
        "match_percentage": round(match_percentage, 1),
        "matches": matches,
        "total_criteria": total_criteria,
        "matching_symptoms": matches,
        "missing_symptoms": total_criteria - matches
    }


def evidence_weigher(diagnoses: list, evidence: dict) -> list:
    """
    Weight diagnoses based on available evidence.
    
    Args:
        diagnoses (list): List of potential diagnoses
        evidence (dict): Supporting evidence for diagnoses
        
    Returns:
        list: Ranked list of diagnoses with weights
    """
    if not isinstance(diagnoses, list) or not isinstance(evidence, dict):
        return []
    
    weighted_diagnoses = []
    
    for diagnosis in diagnoses:
        # Calculate weight based on evidence strength
        weight = 0.5  # Base weight
        
        # Check for supporting evidence
        diagnosis_evidence = evidence.get(diagnosis, {})
        
        # Increase weight based on evidence factors
        if diagnosis_evidence.get("symptom_match", 0) > 70:
            weight += 0.3
        if diagnosis_evidence.get("risk_factors_present", False):
            weight += 0.2
        if diagnosis_evidence.get("typical_presentation", False):
            weight += 0.2
        
        weighted_diagnoses.append({
            "diagnosis": diagnosis,
            "weight": min(weight, 1.0),  # Cap at 1.0
            "evidence": diagnosis_evidence
        })
    
    # Sort by weight (highest first)
    weighted_diagnoses.sort(key=lambda x: x["weight"], reverse=True)
    
    return weighted_diagnoses


def confidence_calculator(diagnosis: str, supporting_evidence: dict) -> float:
    """
    Calculate confidence percentage for a diagnosis.
    
    Args:
        diagnosis (str): Medical diagnosis to evaluate
        supporting_evidence (dict): Evidence supporting this diagnosis
        
    Returns:
        float: Confidence score 0-100%
    """
    if not isinstance(diagnosis, str) or not isinstance(supporting_evidence, dict):
        return 0.0
    
    confidence = 50.0  # Base confidence
    
    # Adjust based on evidence strength
    symptom_match = supporting_evidence.get("symptom_match_percentage", 0)
    confidence += (symptom_match - 50) * 0.5  # Scale symptom match
    
    # Risk factors present
    if supporting_evidence.get("risk_factors_present", False):
        confidence += 15
    
    # Typical presentation
    if supporting_evidence.get("typical_presentation", False):
        confidence += 10
    
    # Age appropriateness
    if supporting_evidence.get("age_appropriate", True):
        confidence += 5
    
    # Ensure confidence stays within bounds
    confidence = max(0.0, min(100.0, confidence))
    
    return round(confidence, 1)


# Paper Analysis Tools

def extract_paper_sections(paper_text: str, max_length: int = 15000) -> dict:
    """
    Extract key sections from full paper text for token-efficient analysis.
    Returns methodology, results, and discussion sections.

    Args:
        paper_text (str): Full paper text
        max_length (int): Max chars per section (default 15K for token efficiency)

    Returns:
        dict: Extracted sections with actual text content
    """
    import os
    debug = os.getenv('DEBUG_PROMPTS') == '1'

    if debug:
        print("\n" + "="*60)
        print("DEBUG: extract_paper_sections called")
        print(f"Input length: {len(paper_text) if isinstance(paper_text, str) else 'NOT A STRING'}")
        if isinstance(paper_text, str):
            print(f"First 300 chars: {paper_text[:300]}...")
        print("="*60 + "\n")

    if not isinstance(paper_text, str):
        return {"error": "Invalid input"}

    text_lower = paper_text.lower()

    # Find section boundaries using common headings
    sections = {
        "methodology": "",
        "results": "",
        "discussion": "",
        "introduction": ""
    }

    # Common section markers
    section_markers = {
        "methodology": ["method", "approach", "implementation", "experimental setup", "materials and methods"],
        "results": ["result", "evaluation", "experiment", "performance"],
        "discussion": ["discussion", "conclusion", "future work"],
        "introduction": ["introduction", "background"]
    }

    # Simple extraction: find paragraphs containing section keywords
    # This is a heuristic approach - works reasonably well for arXiv papers
    paragraphs = paper_text.split('\n\n')

    for section_name, keywords in section_markers.items():
        section_paras = []
        for para in paragraphs:
            if len(para) < 50:  # Skip very short paragraphs
                continue
            para_lower = para.lower()
            # Check if paragraph is in this section
            if any(keyword in para_lower for keyword in keywords):
                section_paras.append(para)
                if len('\n\n'.join(section_paras)) > max_length:
                    break

        sections[section_name] = '\n\n'.join(section_paras)[:max_length]

    # If sections are empty, return first N chars as fallback
    if not any(sections.values()):
        sections["full_text_sample"] = paper_text[:max_length]

    result = {
        "methodology_section": sections["methodology"],
        "results_section": sections["results"],
        "discussion_section": sections["discussion"],
        "introduction_section": sections["introduction"],
        "total_chars": sum(len(s) for s in sections.values())
    }

    if debug:
        print("\n" + "="*60)
        print("DEBUG: extract_paper_sections output")
        print(f"Methodology section: {len(result['methodology_section'])} chars")
        print(f"Results section: {len(result['results_section'])} chars")
        print(f"Discussion section: {len(result['discussion_section'])} chars")
        print(f"Total extracted: {result['total_chars']} chars")
        if result['methodology_section']:
            print(f"First 200 chars of methodology: {result['methodology_section'][:200]}...")
        print("="*60 + "\n")

    return result


def arxiv_search(start_date: str, end_date: str, category: str = None) -> list:
    """
    Search ArXiv for papers by date range and category.
    
    Args:
        start_date (str): Start date (YYYY-MM-DD)
        end_date (str): End date (YYYY-MM-DD)
        category (str): ArXiv category (e.g., cs.AI, cs.LG)
        
    Returns:
        list: List of paper metadata
    """
    # Simplified for now - could integrate with actual ArXiv API
    return [{"message": "ArXiv search tool - integrate with ArXiv API for live search"}]


def abstract_parser(abstract: str) -> dict:
    """
    Extract structured information from paper abstract.

    Args:
        abstract (str): Paper abstract text

    Returns:
        dict: Structured information extracted from abstract including actual content
    """
    import os
    debug = os.getenv('DEBUG_PROMPTS') == '1'

    if debug:
        print("\n" + "="*60)
        print("DEBUG: abstract_parser called")
        print(f"Input length: {len(abstract) if isinstance(abstract, str) else 'NOT A STRING'}")
        if isinstance(abstract, str):
            print(f"First 200 chars: {abstract[:200]}...")
        print("="*60 + "\n")

    if not isinstance(abstract, str):
        return {"error": "Invalid input"}

    # Return the ACTUAL abstract text along with analysis
    # This gives agents real content to work with, not just flags
    result = {
        "abstract_text": abstract,  # CRITICAL: Include actual text
        "length": len(abstract),
        "word_count": len(abstract.split()),
        "has_methodology": any(word in abstract.lower() for word in ["method", "approach", "technique", "algorithm"]),
        "has_results": any(word in abstract.lower() for word in ["result", "performance", "accuracy", "improvement"]),
        "has_contribution": any(word in abstract.lower() for word in ["propose", "introduce", "present", "novel"]),
    }

    if debug:
        print("\n" + "="*60)
        print("DEBUG: abstract_parser output")
        print(f"Returning abstract_text of length: {len(result['abstract_text'])}")
        print(f"First 200 chars of abstract_text: {result['abstract_text'][:200]}...")
        print("="*60 + "\n")

    return result


def methodology_evaluator(paper_text: str) -> dict:
    """
    Evaluate research methodology quality and rigor from full paper text.
    
    Args:
        paper_text (str): Full paper text including methodology section
        
    Returns:
        dict: Methodology evaluation with scores
    """
    if not isinstance(paper_text, str):
        return {"error": "Invalid input", "score": 0}
    
    score = 50  # Base score
    
    # Check for methodology indicators
    method_keywords = ["experiment", "dataset", "baseline", "evaluation", "validation", "test"]
    rigor_keywords = ["statistical", "significance", "reproducible", "ablation", "cross-validation"]
    
    text_lower = paper_text.lower()
    
    # Increase score for methodology indicators
    for keyword in method_keywords:
        if keyword in text_lower:
            score += 5
    
    for keyword in rigor_keywords:
        if keyword in text_lower:
            score += 10
    
    # Cap at 100
    score = min(score, 100)
    
    return {
        "methodology_score": score,
        "has_experiments": "experiment" in text_lower,
        "has_baselines": "baseline" in text_lower,
        "has_statistical_analysis": "statistical" in text_lower or "significance" in text_lower,
        "mentions_reproducibility": "reproducib" in text_lower
    }


def novelty_scorer(paper_content: str, field: str) -> dict:
    """
    Score the novelty and innovation level of research.
    
    Args:
        paper_content (str): Paper content to assess
        field (str): Research field for context
        
    Returns:
        dict: Novelty assessment with score
    """
    if not isinstance(paper_content, str):
        return {"error": "Invalid input", "score": 0}
    
    score = 40  # Base score
    
    # Check for novelty indicators
    novelty_keywords = ["novel", "new", "first", "original", "unprecedented", "innovative"]
    contribution_keywords = ["propose", "introduce", "present", "develop", "design"]
    
    text_lower = paper_content.lower()
    
    # Increase score for novelty indicators
    for keyword in novelty_keywords:
        if keyword in text_lower:
            score += 8
    
    for keyword in contribution_keywords:
        if keyword in text_lower:
            score += 5
    
    # Cap at 100
    score = min(score, 100)
    
    return {
        "novelty_score": score,
        "field": field,
        "claims_novelty": any(kw in text_lower for kw in novelty_keywords),
        "has_contributions": any(kw in text_lower for kw in contribution_keywords)
    }


def field_trend_analyzer(field: str, keywords: list = None) -> dict:
    """
    Analyze current trends and hot topics in research field.
    
    Args:
        field (str): Research field to analyze
        keywords (list): Keywords from the paper
        
    Returns:
        dict: Field trend analysis
    """
    if not isinstance(field, str):
        return {"error": "Invalid input"}
    
    # Simplified trend analysis
    hot_topics = {
        "cs.AI": ["large language models", "transformers", "reinforcement learning", "multimodal"],
        "cs.LG": ["deep learning", "neural networks", "optimization", "generative models"],
        "cs.CL": ["NLP", "language models", "transformers", "text generation"],
        "cs.CV": ["vision transformers", "diffusion models", "object detection", "image generation"]
    }
    
    field_topics = hot_topics.get(field, [])
    
    # Check keyword relevance
    relevance_score = 50
    if keywords:
        keyword_str = " ".join(keywords).lower()
        matching_topics = [topic for topic in field_topics if topic in keyword_str]
        relevance_score += len(matching_topics) * 10
        relevance_score = min(relevance_score, 100)
    
    return {
        "field": field,
        "hot_topics": field_topics,
        "relevance_score": relevance_score,
        "keyword_matches": len([topic for topic in field_topics if keywords and topic in " ".join(keywords).lower()]) if keywords else 0
    }


def citation_impact_predictor(methodology_score: float, novelty_score: float, field_relevance: float, clarity_score: float = 70) -> dict:
    """
    Predict citation impact category based on analysis scores.

    CALIBRATED on 37 ArXiv papers (April-Aug 2024, ~17 months old):
    - Median citations: 4
    - 59.5% have 1-5 citations
    - 86.5% have ≤15 citations
    - Only 2.7% have >50 citations

    Args:
        methodology_score (float): Methodology quality score (0-100)
        novelty_score (float): Novelty score (0-100)
        field_relevance (float): Field relevance score (0-100)
        clarity_score (float): Writing clarity score (0-100)

    Returns:
        dict: Citation prediction with category, range, and confidence
    """
    # Weighted average of scores
    weights = {
        'methodology': 0.30,
        'novelty': 0.35,
        'field_relevance': 0.25,
        'clarity': 0.10
    }

    overall_score = (
        methodology_score * weights['methodology'] +
        novelty_score * weights['novelty'] +
        field_relevance * weights['field_relevance'] +
        clarity_score * weights['clarity']
    )

    # Map score to REALISTIC citation ranges (based on actual data)
    # Using ranges instead of point estimates
    if overall_score >= 85:
        category = "Very High (Top 3%)"
        citation_range = "40-70"
        predicted_citations = 50
    elif overall_score >= 70:
        category = "High (Top 15%)"
        citation_range = "15-40"
        predicted_citations = 25
    elif overall_score >= 55:
        category = "Medium (Top 40%)"
        citation_range = "6-15"
        predicted_citations = 10
    else:
        category = "Low (Bottom 60%)"
        citation_range = "1-5"
        predicted_citations = 3

    # Confidence based on score consistency
    score_variance = max(methodology_score, novelty_score, field_relevance) - min(methodology_score, novelty_score, field_relevance)
    confidence = 100 - (score_variance * 0.5)
    confidence = max(50, min(95, confidence))

    return {
        "category": category,
        "citation_range": citation_range,
        "predicted_citations": predicted_citations,
        "confidence": round(confidence, 1),
        "overall_score": round(overall_score, 1),
        "component_scores": {
            "methodology": methodology_score,
            "novelty": novelty_score,
            "field_relevance": field_relevance,
            "clarity": clarity_score
        },
        "note": "Predictions are for ~17 months after publication, based on 37 ArXiv papers"
    }


# Research Gap Analysis Tools

def extract_key_sections(paper_text: str, paper_id: str) -> dict:
    """
    Extract abstract, introduction, and conclusion from paper text for token-efficient analysis.

    Args:
        paper_text (str): Full paper text
        paper_id (str): Paper identifier for tracking (e.g., '[1]', '[2]')

    Returns:
        dict: Extracted sections with paper ID
    """
    if not isinstance(paper_text, str):
        return {"error": "Invalid input", "paper_id": paper_id}

    text_lower = paper_text.lower()

    # Find section boundaries
    sections = {
        "abstract": "",
        "introduction": "",
        "conclusion": ""
    }

    # Extract abstract (usually at the beginning or marked with "Abstract")
    abstract_match = re.search(r'abstract\s*(.{100,2000}?)(?:\n\n|\n\s*\n|introduction)', text_lower, re.IGNORECASE | re.DOTALL)
    if abstract_match:
        # Find corresponding position in original text (with proper casing)
        start_pos = abstract_match.start(1)
        end_pos = abstract_match.end(1)
        sections["abstract"] = paper_text[start_pos:end_pos].strip()
    else:
        # Fallback: take first 300 words as abstract
        words = paper_text.split()
        sections["abstract"] = " ".join(words[:300])

    # Extract introduction
    intro_match = re.search(r'introduction\s*(.{500,3000}?)(?:\n\n[0-9]|\nmethod|\nrelated work|\napproach)', text_lower, re.IGNORECASE | re.DOTALL)
    if intro_match:
        start_pos = intro_match.start(1)
        end_pos = intro_match.end(1)
        sections["introduction"] = paper_text[start_pos:end_pos].strip()

    # Extract conclusion
    conclusion_match = re.search(r'(conclusion|future work|discussion)\s*(.{300,2000}?)(?:\n\nreferences|\nacknowledg|\nappendix|$)', text_lower, re.IGNORECASE | re.DOTALL)
    if conclusion_match:
        start_pos = conclusion_match.start(2)
        end_pos = conclusion_match.end(2)
        sections["conclusion"] = paper_text[start_pos:end_pos].strip()

    return {
        "paper_id": paper_id,
        "abstract": sections["abstract"][:2000],  # Cap at 2K chars
        "introduction": sections["introduction"][:3000],  # Cap at 3K chars
        "conclusion": sections["conclusion"][:2000],  # Cap at 2K chars
        "total_chars": len(sections["abstract"]) + len(sections["introduction"]) + len(sections["conclusion"])
    }


def extract_paper_metadata(paper_data: str) -> dict:
    """
    Extract title, authors, date, arxiv_id from paper data.

    Args:
        paper_data (str): Paper JSON data or dict as string

    Returns:
        dict: Extracted metadata
    """
    try:
        # Try to parse as JSON if it's a string
        if isinstance(paper_data, str):
            data = json.loads(paper_data)
        else:
            data = paper_data

        return {
            "title": data.get("title", "Unknown"),
            "authors": data.get("authors", "Unknown"),
            "published": data.get("published", "Unknown"),
            "arxiv_id": data.get("id", "Unknown"),
            "category": data.get("category", "Unknown")
        }
    except (json.JSONDecodeError, AttributeError):
        # Fallback: try to extract from string
        title_match = re.search(r'"title":\s*"(.+?)"', paper_data)
        authors_match = re.search(r'"authors":\s*"(.+?)"', paper_data)
        date_match = re.search(r'"published":\s*"(.+?)"', paper_data)
        id_match = re.search(r'"id":\s*"(.+?)"', paper_data)

        return {
            "title": title_match.group(1) if title_match else "Unknown",
            "authors": authors_match.group(1) if authors_match else "Unknown",
            "published": date_match.group(1) if date_match else "Unknown",
            "arxiv_id": id_match.group(1) if id_match else "Unknown",
            "category": "Unknown"
        }


def cluster_approaches(paper_summaries: list) -> dict:
    """
    Identify and group similar research approaches/methodologies across multiple papers.

    Args:
        paper_summaries (list): List of paper summary strings

    Returns:
        dict: Clustered approaches with paper citations
    """
    if not isinstance(paper_summaries, list):
        return {"error": "Invalid input"}

    # Common approach keywords for clustering
    approach_patterns = {
        "Prompting-Based Methods": ["prompt", "prompting", "in-context learning", "few-shot", "zero-shot", "chain-of-thought"],
        "Fine-Tuning Methods": ["fine-tun", "training", "supervised learning", "parameter-efficient", "lora", "adapter"],
        "Retrieval-Augmented": ["retrieval", "rag", "knowledge base", "external memory", "vector database"],
        "Architectural Innovations": ["architecture", "transformer", "attention mechanism", "model design", "neural architecture"],
        "Data-Centric Approaches": ["dataset", "data augmentation", "synthetic data", "data quality", "labeling"],
        "Evaluation & Benchmarking": ["benchmark", "evaluation", "metric", "test set", "comparison"]
    }

    clusters = {approach: [] for approach in approach_patterns.keys()}

    # Assign papers to clusters based on keyword matching
    for idx, summary in enumerate(paper_summaries):
        summary_lower = summary.lower() if isinstance(summary, str) else str(summary).lower()
        paper_id = f"[{idx + 1}]"

        assigned = False
        for approach_name, keywords in approach_patterns.items():
            if any(keyword in summary_lower for keyword in keywords):
                clusters[approach_name].append(paper_id)
                assigned = True

        if not assigned:
            # Create "Other Methods" cluster if needed
            if "Other Methods" not in clusters:
                clusters["Other Methods"] = []
            clusters["Other Methods"].append(paper_id)

    # Remove empty clusters
    clusters = {k: v for k, v in clusters.items() if v}

    return {
        "clusters": clusters,
        "total_approaches": len(clusters),
        "papers_clustered": len(paper_summaries)
    }


def detect_contradictions(paper_summaries: list) -> dict:
    """
    Find conflicting claims, results, or conclusions across papers.

    Args:
        paper_summaries (list): List of paper summary strings with key findings

    Returns:
        dict: Detected contradictions with paper citations
    """
    if not isinstance(paper_summaries, list) or len(paper_summaries) < 2:
        return {"contradictions": [], "note": "Need at least 2 papers to detect contradictions"}

    contradictions = []

    # Keywords that suggest conflicting findings
    positive_keywords = ["improves", "better", "outperforms", "effective", "successful", "works well"]
    negative_keywords = ["fails", "worse", "ineffective", "unsuccessful", "does not work", "limited effectiveness"]

    # Compare papers pairwise for contradictory claims
    for i, summary_i in enumerate(paper_summaries):
        if not isinstance(summary_i, str):
            continue
        summary_i_lower = summary_i.lower()

        for j, summary_j in enumerate(paper_summaries[i+1:], start=i+1):
            if not isinstance(summary_j, str):
                continue
            summary_j_lower = summary_j.lower()

            # Check if papers discuss similar topics but with different conclusions
            # Simple heuristic: both mention same techniques but with opposite sentiment
            common_topics = []
            for topic in ["prompting", "fine-tuning", "retrieval", "transformer", "few-shot"]:
                if topic in summary_i_lower and topic in summary_j_lower:
                    common_topics.append(topic)

            if common_topics:
                # Check if one is positive and one is negative about the same topic
                i_positive = any(kw in summary_i_lower for kw in positive_keywords)
                i_negative = any(kw in summary_i_lower for kw in negative_keywords)
                j_positive = any(kw in summary_j_lower for kw in positive_keywords)
                j_negative = any(kw in summary_j_lower for kw in negative_keywords)

                if (i_positive and j_negative) or (i_negative and j_positive):
                    contradictions.append({
                        "papers": [f"[{i+1}]", f"[{j+1}]"],
                        "topic": ", ".join(common_topics),
                        "type": "conflicting_findings"
                    })

    return {
        "contradictions": contradictions,
        "count": len(contradictions),
        "note": "Contradictions detected using keyword-based heuristics"
    }


def identify_research_gaps(approaches: list, field_context: str, contradictions: list = None) -> dict:
    """
    Identify missing combinations, unexplored directions, and research opportunities.

    Args:
        approaches (list): List of identified approaches from papers
        field_context (str): Research field context
        contradictions (list): List of contradictions found (optional)

    Returns:
        dict: Identified research gaps with categories
    """
    if not isinstance(approaches, list):
        return {"error": "Invalid input"}

    gaps = {
        "methodological_gaps": [],
        "evaluation_gaps": [],
        "application_gaps": [],
        "unresolved_debates": []
    }

    # Methodological gaps: Common technique combinations not explored
    technique_combinations = [
        {"combination": "Retrieval + Fine-tuning", "keywords": ["retrieval", "fine-tun"]},
        {"combination": "Prompting + Architecture modification", "keywords": ["prompt", "architecture"]},
        {"combination": "Data augmentation + Few-shot learning", "keywords": ["data augmentation", "few-shot"]}
    ]

    approaches_str = " ".join([str(a).lower() for a in approaches])

    for combo in technique_combinations:
        keywords_present = [kw for kw in combo["keywords"] if kw in approaches_str]
        if len(keywords_present) == 1:  # Only one part present, not the combination
            gaps["methodological_gaps"].append({
                "gap": f"{combo['combination']} not explored together",
                "evidence": f"Papers explore {keywords_present[0]} but not in combination"
            })

    # Evaluation gaps: Common missing metrics
    common_metrics = ["efficiency", "robustness", "fairness", "interpretability"]
    for metric in common_metrics:
        if metric not in approaches_str:
            gaps["evaluation_gaps"].append({
                "gap": f"Missing {metric} evaluation",
                "evidence": f"No papers explicitly evaluate {metric}"
            })

    # Application gaps: Common domains that might be underexplored
    if "multilingual" not in approaches_str and "language" in field_context.lower():
        gaps["application_gaps"].append({
            "gap": "Limited multilingual evaluation",
            "evidence": "Most papers focus on English only"
        })

    if "low-resource" not in approaches_str:
        gaps["application_gaps"].append({
            "gap": "Low-resource settings underexplored",
            "evidence": "Papers primarily test on large datasets"
        })

    # Unresolved debates from contradictions
    if contradictions:
        for contradiction in contradictions[:3]:  # Limit to top 3
            if isinstance(contradiction, dict):
                gaps["unresolved_debates"].append({
                    "debate": f"Conflicting findings on {contradiction.get('topic', 'unknown')}",
                    "papers": contradiction.get("papers", [])
                })

    # Filter out empty categories
    gaps = {k: v for k, v in gaps.items() if v}

    return {
        "gaps": gaps,
        "total_gaps": sum(len(v) for v in gaps.values()),
        "field": field_context
    }


# Paper section fetching tool (for on-demand section retrieval)
_PAPERS_CACHE = None

def fetch_paper_section(paper_id: str, section: str) -> dict:
    """
    Fetch additional sections (introduction or conclusion) from a paper on demand.

    Args:
        paper_id: Paper identifier like "[1]", "[2]", etc.
        section: Section to fetch - either "introduction" or "conclusion"

    Returns:
        Dictionary with paper_id, section name, and section text
    """
    global _PAPERS_CACHE

    # Load papers from cache or file
    if _PAPERS_CACHE is None:
        import json
        from pathlib import Path
        papers_file = Path(__file__).parent.parent / "setup" / "data" / "gap_analysis_papers.json"
        if papers_file.exists():
            with open(papers_file) as f:
                _PAPERS_CACHE = json.load(f)
        else:
            return {"error": "Papers file not found"}

    # Parse paper ID
    try:
        # Extract number from "[1]", "[2]", etc.
        paper_num = int(paper_id.strip("[]"))
        if paper_num < 1 or paper_num > len(_PAPERS_CACHE):
            return {"error": f"Paper {paper_id} not found. Valid range: [1] to [{len(_PAPERS_CACHE)}]"}

        paper = _PAPERS_CACHE[paper_num - 1]  # 0-indexed

        # Validate section
        if section not in ["introduction", "conclusion"]:
            return {"error": f"Invalid section '{section}'. Must be 'introduction' or 'conclusion'"}

        section_text = paper.get(section, "")
        if not section_text:
            return {
                "paper_id": paper_id,
                "section": section,
                "text": f"No {section} available for this paper"
            }

        return {
            "paper_id": paper_id,
            "title": paper.get("title", "Unknown"),
            "section": section,
            "text": section_text[:5000]  # Cap at 5000 chars for safety
        }

    except (ValueError, IndexError) as e:
        return {"error": f"Invalid paper_id format: {paper_id}. Use format like [1], [2], etc."}


def handoff_to_agent(agent_name: str, message: str = "") -> dict:
    """
    Handoff execution to another agent in the swarm.

    NOTE: This is a compatibility tool for orchestrators that handle handoffs automatically.
    In AutoGen Swarm, handoffs are managed through the framework's built-in mechanisms.
    This tool exists so agents don't error when trying to call it, but the actual
    handoff is performed by the orchestrator's routing logic.

    Args:
        agent_name (str): Name of the agent to hand off to
        message (str): Optional message to pass to the next agent

    Returns:
        dict: Handoff confirmation (actual routing handled by orchestrator)
    """
    import os
    import datetime

    # Debug logging for handoff attempts
    debug = os.getenv('DEBUG_HANDOFFS', '0') == '1'
    if debug:
        timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"\n[{timestamp}] DEBUG: handoff_to_agent called")
        print(f"  → Target agent: {agent_name}")
        print(f"  → Message length: {len(message) if message else 0} chars")
        if message:
            print(f"  → Message preview: {message[:200]}...")
        print()

    return {
        "handoff_requested": True,
        "target_agent": agent_name,
        "message": message,
        "note": "Handoff managed by orchestrator routing"
    }


handoff_to_agent._is_handoff_tool = True


# Specific handoff tools for controlled agent flow
def handoff_to_paper_reader(message: str = "") -> dict:
    """
    Transfer control to the Paper Reading Specialist agent.

    This agent extracts and analyzes paper sections on demand.

    Args:
        message (str): Optional context or request for the Paper Reading agent

    Returns:
        dict: Handoff confirmation
    """
    return handoff_to_agent("Paper Reading Specialist", message)


def handoff_to_approach_analyzer(message: str = "") -> dict:
    """
    Transfer control to the Research Approach Analyzer agent.

    This agent clusters and analyzes research approaches across papers.

    Args:
        message (str): Optional context or findings to pass to the Approach Analyzer

    Returns:
        dict: Handoff confirmation
    """
    return handoff_to_agent("Research Approach Analyzer", message)


def handoff_to_contradiction_detector(message: str = "") -> dict:
    """
    Transfer control to the Contradiction Detection Specialist agent.

    This agent identifies conflicting claims and results across papers.

    Args:
        message (str): Optional context or approaches to check for contradictions

    Returns:
        dict: Handoff confirmation
    """
    return handoff_to_agent("Contradiction Detection Specialist", message)


def handoff_to_gap_synthesizer(message: str = "") -> dict:
    """
    Transfer control to the Research Gap Synthesizer agent.

    This agent synthesizes all findings to identify research gaps and opportunities.

    Args:
        message (str): Optional summary of findings to synthesize

    Returns:
        dict: Handoff confirmation
    """
    return handoff_to_agent("Research Gap Synthesizer", message)
