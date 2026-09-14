"""Satellite gates. Each reads one satellite's file contract and attaches it to
the matching candidate under its own namespace in schema/v1.json. Never a Python
import across repos -- only files, so any satellite can be broken or mid-refactor
without taking down the spine.
"""
