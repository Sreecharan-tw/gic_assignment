"""
Data Layer Module - Database and Data Ingestion

This module handles:
- Database connection and operations (database.py)
- CSV data parsing and ingestion (ingest.py)
"""

from .database import Database
from .ingest import DataIngestion

__all__ = ['Database', 'DataIngestion']
