# integrations/companies_house.py
import requests
import pandas as pd
import time
from typing import Optional, Dict
import os
from dotenv import load_dotenv

# Load API key from .env file
load_dotenv()
API_KEY = os.getenv('COMPANIES_HOUSE_API_KEY')
BASE_URL = "https://api.company-information.service.gov.uk"

# Simple cache to avoid duplicate API calls
_cache = {}

def search_company(company_name: str) -> Optional[Dict]:
    """
    Search for a company by name and return its basic details.
    Returns None if not found or on error.
    """
    # Check cache first
    if company_name in _cache:
        return _cache[company_name]
    
    if not API_KEY:
        print("⚠️  COMPANIES_HOUSE_API_KEY not set in .env file")
        return None
    
    headers = {
        'Authorization': f'Basic {API_KEY}',
        'Accept': 'application/json'
    }
    
    # Clean the name for search
    search_term = company_name.split('(')[0].strip().upper()
    
    try:
        response = requests.get(
            f"{BASE_URL}/search/companies",
            headers=headers,
            params={'q': search_term, 'items_per_page': 5}
        )
        response.raise_for_status()
        
        results = response.json().get('items', [])
        if results:
            # Get the best match (first result)
            best_match = results[0]
            company_data = {
                'company_name': best_match.get('title', ''),
                'company_number': best_match.get('company_number', ''),
                'company_status': best_match.get('company_status', ''),
                'company_type': best_match.get('company_type', ''),
                'address': best_match.get('address_snippet', '').replace('<br/>', ', '),
                'date_of_creation': best_match.get('date_of_creation', ''),
                'match_score': best_match.get('matches', {}).get('title', [0])[0]
            }
            
            # Cache the result
            _cache[company_name] = company_data
            return company_data
        
    except requests.exceptions.RequestException as e:
        print(f"❌ API error for '{company_name}': {e}")
    except Exception as e:
        print(f"❌ Unexpected error for '{company_name}': {e}")
    
    _cache[company_name] = None
    return None

def verify_supplier(supplier_name: str) -> Dict:
    """
    Main function to verify a supplier against Companies House.
    Returns a standardized result dict.
    """
    # Initialize result structure
    result = {
        'supplier_name': supplier_name,
        'is_company': False,
        'company_number': None,
        'company_status': None,
        'company_type': None,
        'confidence': 'low',
        'entity_type': 'unknown'  # New field to classify the entity
    }
    
    # === NEW SMART FILTER: Skip obvious public sector bodies ===
    public_sector_keywords = [
        'council', 'borough council', 'city council', 'county council',
        'authority', 'government', 'department', 'ministry',
        'nhs', 'hospital', 'health trust', 'health board',
        'trust', 'police', 'fire', 'ambulance',
        'commission', 'agency', 'assembly', 'parliament'
    ]
    
    supplier_lower = supplier_name.lower()
    
    # Check if this looks like a public sector body
    for keyword in public_sector_keywords:
        if keyword in supplier_lower:
            result['entity_type'] = 'public_sector'
            result['notes'] = f'Public sector body (contains "{keyword}")'
            print(f"⏭️  Skipping API call for public body: '{supplier_name}'")
            return result  # Skip the API call entirely
    
    # Also skip generic or placeholder names
    skip_names = ['not specified', 'unknown', 'confidential', 'redacted', 'nan', 'none', '']
    if supplier_lower in skip_names or 'supplier name redacted' in supplier_lower:
        result['entity_type'] = 'placeholder'
        result['notes'] = 'Placeholder or redacted name'
        return result
    
    # === ONLY NOW proceed with Companies House API call ===
    print(f"🔍 API lookup for potential company: '{supplier_name}'")
    company_data = search_company(supplier_name)
    
    if company_data:
        result.update({
            'is_company': True,
            'company_number': company_data['company_number'],
            'company_status': company_data['company_status'],
            'company_type': company_data['company_type'],
            'confidence': 'high' if company_data['match_score'] > 5 else 'medium',
            'entity_type': 'registered_company',
            'official_name': company_data['company_name'],
            'registered_address': company_data['address']
        })
    else:
        result['entity_type'] = 'unknown_commercial'
        result['notes'] = 'Not found as registered company - could be sole trader, charity, or unregistered business'
    
    return result
    
    company_data = search_company(supplier_name)
    
    if company_data:
        result.update({
            'is_company': True,
            'company_number': company_data['company_number'],
            'company_status': company_data['company_status'],
            'company_type': company_data['company_type'],
            'confidence': 'high' if company_data['match_score'] > 5 else 'medium',
            'official_name': company_data['company_name'],
            'registered_address': company_data['address']
        })
    else:
        result['notes'] = 'Not found in Companies House'
    
    return result

# For bulk processing in your analyzer
def enrich_suppliers_dataframe(df: pd.DataFrame, supplier_col: str = 'supplier') -> pd.DataFrame:
    """Add Companies House verification columns to a DataFrame."""
    print(f"🔍 Smart verification of {len(df[supplier_col].unique())} unique names...")
    
    # ... [your existing cache and progress loop] ...
    
    # Add columns to dataframe - ADD THE NEW COLUMN
    df['entity_type'] = df[supplier_col].map(
        lambda x: verification_results.get(str(x), {}).get('entity_type', 'unknown')
    )
    df['company_status'] = df[supplier_col].map(
        lambda x: verification_results.get(str(x), {}).get('company_status', 'UNKNOWN')
    )
    df['company_type'] = df[supplier_col].map(
        lambda x: verification_results.get(str(x), {}).get('company_type', 'UNKNOWN')
    )
    df['is_verified_company'] = df[supplier_col].map(
        lambda x: verification_results.get(str(x), {}).get('is_company', False)
    )
    
    # Print summary
    entity_counts = df['entity_type'].value_counts()
    print(f"📊 Entity classification: {entity_counts.to_dict()}")
    
    return df