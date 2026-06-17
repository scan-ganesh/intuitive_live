from google.cloud import firestore
import pandas as pd

syminfo_cache = {}

def _get_underlying_reference_data(underlying):
    """Helper: Fetch and cache reference data for an underlying (lot_size, exchange, options expiries)"""
    if underlying in syminfo_cache:
        print(f"Using cached reference data for {underlying}")
        return syminfo_cache[underlying]
    
    db = firestore.Client()
    collection_ref = db.collection('references/COMMON/EXPIRYDATES')
    doc_ref = collection_ref.document(underlying)
    doc_snapshot = doc_ref.get()
    
    if not doc_snapshot.exists:
        print(f"No expiry data found in Firestore for underlying: {underlying}")
        return None

    data = doc_snapshot.to_dict()
    
    cached_data = {
        'lot_size': data.get('lot_size', 0),
        'exchange': data.get('exchange', ''),
        'options': sorted(list(data.get('options', [])))
    }
    
    syminfo_cache[underlying] = cached_data
    return cached_data

def get_next_expiry_date_v2(date, underlying):
    """Get next expiry date after the given date for the underlying. 
    Returns a tuple: (expiry_date, is_last_in_month)
    where is_last_in_month is True if the returned expiry is the last one in its month 
    (i.e., the next expiry after it falls in a different month, or there is no next expiry).
    """
    ref_data = _get_underlying_reference_data(underlying)
    if not ref_data:
        return None
    
    all_expiries = ref_data['options']
    if not all_expiries:
        return None
    
    date_dt = pd.to_datetime(date)
    expiry_dts = [pd.to_datetime(exp) for exp in all_expiries]
    
    # Find the first expiry strictly after the given date
    next_expiry = None
    next_idx = None
    for i, exp_dt in enumerate(expiry_dts):
        if exp_dt > date_dt:
            next_expiry = all_expiries[i]  # keep original string format
            next_idx = i
            break
    
    if next_expiry is None:
        return None
    
    # Check if this is the last expiry in its month
    is_last_in_month = True
    if next_idx is not None and next_idx + 1 < len(expiry_dts):
        next_next_dt = expiry_dts[next_idx + 1]
        current_month = pd.to_datetime(next_expiry).month
        next_month = next_next_dt.month
        if current_month == next_month and next_next_dt.year == pd.to_datetime(next_expiry).year:
            is_last_in_month = False
    
    return next_expiry, is_last_in_month