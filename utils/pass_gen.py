# Password generation
"""Password generation utilities for Elysium Trading Platform"""

import random
import string
import secrets

def generate_secure_password(length: int = 16, include_special: bool = True) -> str:
    """
    Generate a secure random password
    
    Args:
        length: Password length (default: 16)
        include_special: Whether to include special characters (default: True)
        
    Returns:
        Secure random password
    """
    # Define character sets
    lowercase = string.ascii_lowercase
    uppercase = string.ascii_uppercase
    digits = string.digits
    special = string.punctuation if include_special else ""
    
    # Ensure password contains at least one of each character type
    password = [
        secrets.choice(lowercase),
        secrets.choice(uppercase),
        secrets.choice(digits)
    ]
    
    if include_special:
        password.append(secrets.choice(special))
    
    # Fill the remaining length with random characters
    all_chars = lowercase + uppercase + digits + special
    password.extend(secrets.choice(all_chars) for _ in range(length - len(password)))
    
    # Shuffle the password characters
    random.shuffle(password)
    
    return ''.join(password)

def generate_wallet_key() -> str:
    """
    Generate a secure private key for wallet (hex string)
    
    Returns:
        Secure wallet key
    """
    # Generate 32 random bytes and convert to hex
    private_key = secrets.token_bytes(32).hex()
    return "0x" + private_key

def generate_mnemonic(words: int = 12) -> str:
    """
    Generate a mnemonic phrase
    
    Args:
        words: Number of words in the mnemonic (default: 12)
        
    Returns:
        Space-separated mnemonic phrase
    """
    # Load BIP-39 wordlist
    wordlist = [
        "abandon", "ability", "able", "about", "above", "absent", "absorb", "abstract", 
        "absurd", "abuse", "access", "accident", "account", "accuse", "achieve", "acid", 
        "acoustic", "acquire", "across", "act", "action", "actor", "actress", "actual", 
        "adapt", "add", "addict", "address", "adjust", "admit", "adult", "advance", 
        "advice", "aerobic", "affair", "afford", "afraid", "again", "age", "agent", 
        "agree", "ahead", "aim", "air", "airport", "aisle", "alarm", "album", 
        "alcohol", "alert", "alien", "all", "alley", "allow", "almost", "alone", 
        "alpha", "already", "also", "alter", "always", "amateur", "amazing", "among", 
        "amount", "amused", "analyst", "anchor", "ancient", "anger", "angle", "angry", 
        "animal", "ankle", "announce", "annual", "another", "answer", "antenna", "antique", 
        "anxiety", "any", "apart", "apology", "appear", "apple", "approve", "april", 
        "arch", "arctic", "area", "arena", "argue", "arm", "armed", "armor", 
        "army", "around", "arrange", "arrest", "arrive", "arrow", "art", "artefact", 
        "artist", "artwork", "ask", "aspect", "assault", "asset", "assist", "assume", 
        "asthma", "athlete", "atom", "attack", "attend", "attitude", "attract", "auction", 
        "audit", "august", "aunt", "author", "auto", "autumn", "average", "avocado", 
        # ... more words would be included in a real implementation
    ]
    
    # In a real implementation, you would ensure the wordlist is complete and valid
    # This is just an example with a partial list
    
    # Generate random indices into the wordlist
    indices = [secrets.randbelow(len(wordlist)) for _ in range(words)]
    
    # Look up the words
    selected_words = [wordlist[i] for i in indices]
    
    # Join with spaces
    return " ".join(selected_words)