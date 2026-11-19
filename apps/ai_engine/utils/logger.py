"""
Logging configuration utility.
"""
import logging
import os
import sys

def get_logger(name: str) -> logging.Logger:
    """
    Configures and returns a logger.
    Outputs to console and file (logs/ai_engine.log).
    Log level from env or default INFO.
    """
    logger = logging.getLogger(name)
    
    # Avoid duplicating handlers if logger is already configured
    if not logger.handlers:
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        logger.setLevel(log_level)
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Console handler
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        
        # File handler
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        fh = logging.FileHandler(os.path.join(log_dir, "ai_engine.log"))
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        
    return logger
