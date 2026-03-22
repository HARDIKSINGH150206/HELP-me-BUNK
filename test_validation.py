#!/usr/bin/env python3
"""
Test script for input validation functions
Verifies that sanitization and validation work correctly
"""

import sys
sys.path.insert(0, '/home/hardik-singh/Documents/VScode/Code/attendance-project')

from app import (
    sanitize_string, validate_email, validate_integer, 
    validate_day_of_week, validate_time_format, validate_percentage
)

def test_sanitize_string():
    """Test XSS prevention"""
    print("Testing sanitize_string()...")
    
    # Normal input
    assert sanitize_string("Computer Science") == "Computer Science"
    print("  ✓ Normal text passed")
    
    # XSS attempt - should be rejected
    result = sanitize_string("<script>alert('xss')</script>")
    assert result is None
    print("  ✓ XSS payload rejected")
    
    # HTML entities in safe text should be escaped
    result = sanitize_string("Tom & Jerry")
    assert result is not None
    assert "&amp;" in result
    print("  ✓ HTML entities escaped")
    
    # Max length - should truncate
    long_text = "a" * 300
    result = sanitize_string(long_text, max_length=255)
    assert result is not None
    assert len(result) == 255
    print("  ✓ Max length enforced (truncation)")
    
    # Dangerous pattern - should be rejected
    result = sanitize_string("onclick='alert(1)'")
    assert result is None
    print("  ✓ Dangerous pattern rejected")
    
    # JavaScript: pattern - should be rejected
    result = sanitize_string("javascript:void(0)")
    assert result is None
    print("  ✓ JavaScript protocol rejected")

def test_validate_integer():
    """Test integer validation"""
    print("\nTesting validate_integer()...")
    
    # Valid integer
    assert validate_integer(5, min_val=0, max_val=10) == 5
    print("  ✓ Valid integer (5) accepted")
    
    # Out of range
    assert validate_integer(15, min_val=0, max_val=10) is None
    print("  ✓ Out of range (15) rejected")
    
    # Negative
    assert validate_integer(-1, min_val=0, max_val=10) is None
    print("  ✓ Negative value rejected")
    
    # String that's a number
    assert validate_integer("42", min_val=0, max_val=100) == 42
    print("  ✓ String number '42' converted")
    
    # Invalid string
    assert validate_integer("abc", min_val=0, max_val=100) is None
    print("  ✓ Non-numeric string rejected")

def test_validate_day_of_week():
    """Test day validation"""
    print("\nTesting validate_day_of_week()...")
    
    # Valid days
    for day in range(0, 7):
        assert validate_day_of_week(day) == day
    print("  ✓ Valid days (0-6) accepted")
    
    # Out of range
    assert validate_day_of_week(7) is None
    print("  ✓ Day 7 rejected")
    
    assert validate_day_of_week(-1) is None
    print("  ✓ Day -1 rejected")
    
    # Different types
    assert validate_day_of_week("3") == 3
    print("  ✓ String '3' converted")

def test_validate_time_format():
    """Test time format validation"""
    print("\nTesting validate_time_format()...")
    
    # Valid times
    assert validate_time_format("09:30") == True
    print("  ✓ Time '09:30' accepted")
    
    assert validate_time_format("23:59") == True
    print("  ✓ Time '23:59' accepted")
    
    assert validate_time_format("00:00") == True
    print("  ✓ Time '00:00' accepted")
    
    # Invalid times
    assert validate_time_format("25:00") == False
    print("  ✓ Time '25:00' rejected")
    
    assert validate_time_format("12:60") == False
    print("  ✓ Time '12:60' rejected")
    
    assert validate_time_format("9:30") == False
    print("  ✓ Time '9:30' (missing leading 0) rejected")
    
    assert validate_time_format("13:30:45") == False
    print("  ✓ Time with seconds rejected")

def test_validate_email():
    """Test email validation"""
    print("\nTesting validate_email()...")
    
    # Valid emails
    assert validate_email("user@example.com") == True
    print("  ✓ Email 'user@example.com' accepted")
    
    assert validate_email("test.user+tag@domain.co.uk") == True
    print("  ✓ Email 'test.user+tag@domain.co.uk' accepted")
    
    # Invalid emails
    assert validate_email("invalid.email") == False
    print("  ✓ Email without @ rejected")
    
    assert validate_email("@example.com") == False
    print("  ✓ Email without local part rejected")
    
    assert validate_email("user@") == False
    print("  ✓ Email without domain rejected")

def test_validate_percentage():
    """Test percentage validation"""
    print("\nTesting validate_percentage()...")
    
    # Valid percentages
    assert validate_percentage(75) == 75
    print("  ✓ Percentage 75 accepted")
    
    assert validate_percentage(0) == 0
    print("  ✓ Percentage 0 accepted")
    
    assert validate_percentage(100) == 100
    print("  ✓ Percentage 100 accepted")
    
    # Out of range
    assert validate_percentage(-1) is None
    print("  ✓ Negative percentage rejected")
    
    assert validate_percentage(101) is None
    print("  ✓ Percentage > 100 rejected")
    
    # String percentage
    assert validate_percentage("50") == 50
    print("  ✓ String '50' converted")

def main():
    """Run all tests"""
    print("\n" + "="*50)
    print("   Input Validation Test Suite")
    print("="*50)
    
    try:
        test_sanitize_string()
        test_validate_integer()
        test_validate_day_of_week()
        test_validate_time_format()
        test_validate_email()
        test_validate_percentage()
        
        print("\n" + "="*50)
        print("✓ All validation tests passed!")
        print("="*50 + "\n")
        return 0
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        return 1

if __name__ == '__main__':
    sys.exit(main())
