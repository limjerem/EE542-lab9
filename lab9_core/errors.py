"""Actionable API errors without echoing credentials or provider response bodies."""
def user_error(error):
    body=getattr(error,'body',{}) or {}
    if isinstance(body,dict) and isinstance(body.get('error'),dict):body=body['error']
    code=body.get('code') if isinstance(body,dict) else None
    if code=='credit_balance_exhausted':
        return 'OpenAI API credits are exhausted. Add API credits or configure a funded key before retrying.'
    if isinstance(body,dict) and body.get('type')=='insufficient_quota':
        return 'OpenAI API quota is unavailable. Check the API account credits and limits before retrying.'
    if getattr(error,'status_code',None)==401:
        return 'OpenAI rejected the API key. Check your local API configuration.'
    return type(error).__name__
