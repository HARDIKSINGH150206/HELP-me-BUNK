#!/usr/bin/env python3
"""
Attendance Calculator & Bunk Advisor
Calculates safe bunking strategy to maintain 75% attendance
"""

import json
from datetime import datetime
from colorama import init, Fore, Style

# Initialize colorama for colored terminal output
init(autoreset=True)

class AttendanceCalculator:
    def __init__(self, target_percentage=75.0, safety_buffer=1.0):
        """
        Initialize calculator
        target_percentage: Minimum required attendance (default 75%)
        safety_buffer: Extra buffer to maintain (default 1%)
        """
        self.target_percentage = target_percentage
        self.safe_target = target_percentage + safety_buffer
        self.attendance_data = []
    
    def load_data(self, filename):
        """Load attendance data from JSON file"""
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
                self.attendance_data = data.get('data', [])
                print(f"{Fore.GREEN}✓ Loaded data from {filename}")
                return True
        except FileNotFoundError:
            print(f"{Fore.RED}✗ File not found: {filename}")
            return False
        except json.JSONDecodeError:
            print(f"{Fore.RED}✗ Invalid JSON file")
            return False
    
    def calculate_bunk_allowance(self, present, total, future_classes=0):
        """
        Calculate how many classes can be safely skipped
        
        Args:
            present: Classes attended
            total: Total classes conducted
            future_classes: Expected future classes in semester
        
        Returns:
            Dictionary with calculation details
        """
        current_percentage = (present / total * 100) if total > 0 else 0
        
        # Calculate maximum classes that can be missed
        total_future = total + future_classes
        max_bunks = 0
        
        # Calculate bunks while maintaining safe target
        for bunks in range(future_classes + 1):
            new_total = total + future_classes
            new_percentage = (present / new_total) * 100
            
            if new_percentage >= self.safe_target:
                max_bunks = bunks
            else:
                break
        
        # How many more classes needed to attend to reach safe zone if below
        classes_needed = 0
        if current_percentage < self.safe_target:
            classes_needed = max(0, int((self.safe_target * total - 100 * present) / 
                                       (100 - self.safe_target)) + 1)
        
        return {
            'present': present,
            'total': total,
            'current_percentage': round(current_percentage, 2),
            'max_safe_bunks': max_bunks,
            'classes_needed_if_below': classes_needed,
            'is_safe': current_percentage >= self.safe_target,
            'buffer': round(current_percentage - self.target_percentage, 2)
        }
    
    def analyze_all_subjects(self, future_classes=20):
        """Analyze all subjects and provide recommendations"""
        print(f"\n{'='*70}")
        print(f"{Fore.CYAN}{Style.BRIGHT}ATTENDANCE ANALYSIS & BUNK STRATEGY")
        print(f"{'='*70}")
        print(f"Target: {self.target_percentage}% (Safe Zone: {self.safe_target}%)")
        print(f"Assuming {future_classes} more classes per subject this semester\n")
        
        results = []
        
        for subject in self.attendance_data:
            name = subject.get('subject', 'Unknown')
            present = subject.get('present', 0)
            total = subject.get('total', 0)
            
            analysis = self.calculate_bunk_allowance(present, total, future_classes)
            analysis['subject'] = name
            results.append(analysis)
            
            # Print subject analysis
            self._print_subject_analysis(analysis)
        
        return results
    
    def _print_subject_analysis(self, analysis):
        """Print formatted analysis for a single subject"""
        subject = analysis['subject']
        current = analysis['current_percentage']
        present = analysis['present']
        total = analysis['total']
        max_bunks = analysis['max_safe_bunks']
        is_safe = analysis['is_safe']
        buffer = analysis['buffer']
        needed = analysis['classes_needed_if_below']
        
        # Color coding based on status
        if current >= self.safe_target:
            status_color = Fore.GREEN
            status = "✓ SAFE"
        elif current >= self.target_percentage:
            status_color = Fore.YELLOW
            status = "⚠ WARNING"
        else:
            status_color = Fore.RED
            status = "✗ DANGER"
        
        print(f"{Style.BRIGHT}{subject}")
        print(f"  Current: {present}/{total} ({status_color}{current}%{Style.RESET_ALL}) {status_color}{status}")
        print(f"  Buffer: {'+' if buffer >= 0 else ''}{buffer}% from minimum")
        
        if is_safe and max_bunks > 0:
            print(f"  {Fore.GREEN}→ You can safely bunk {max_bunks} more classes")
        elif needed > 0:
            print(f"  {Fore.RED}→ You need to attend {needed} more classes to be safe!")
        else:
            print(f"  {Fore.YELLOW}→ Attend all remaining classes to maintain attendance")
        
        print()
    
    def get_overall_recommendation(self, results):
        """Provide overall bunking strategy"""
        print(f"\n{'='*70}")
        print(f"{Fore.CYAN}{Style.BRIGHT}OVERALL RECOMMENDATION")
        print(f"{'='*70}\n")
        
        danger_subjects = [r for r in results if r['current_percentage'] < self.target_percentage]
        warning_subjects = [r for r in results if self.target_percentage <= r['current_percentage'] < self.safe_target]
        safe_subjects = [r for r in results if r['current_percentage'] >= self.safe_target]
        
        if danger_subjects:
            print(f"{Fore.RED}⚠ CRITICAL: You're below 75% in {len(danger_subjects)} subject(s)!")
            print("Priority: Attend ALL classes for:")
            for subj in danger_subjects:
                print(f"  • {subj['subject']}: Need {subj['classes_needed_if_below']} more classes")
            print()
        
        if warning_subjects:
            print(f"{Fore.YELLOW}⚠ WARNING: {len(warning_subjects)} subject(s) need attention")
            print("Be careful with:")
            for subj in warning_subjects:
                print(f"  • {subj['subject']}: Only {subj['buffer']:.1f}% buffer")
            print()
        
        if safe_subjects:
            print(f"{Fore.GREEN}✓ SAFE to bunk in {len(safe_subjects)} subject(s):")
            bunkable = sorted([s for s in safe_subjects if s['max_safe_bunks'] > 0], 
                            key=lambda x: x['max_safe_bunks'], reverse=True)
            
            for subj in bunkable:
                print(f"  • {subj['subject']}: Up to {subj['max_safe_bunks']} classes")
            
            if not bunkable:
                print(f"  {Fore.YELLOW}(But recommended to attend all to maintain buffer)")


def main():
    # Try to find the most recent attendance file
    import glob
    import os
    
    attendance_files = glob.glob("attendance_*.json")
    
    if not attendance_files:
        print(f"{Fore.RED}✗ No attendance data found!")
        print("Please run the scraper first: python3 attendance_scraper.py")
        return
    
    # Use most recent file
    latest_file = max(attendance_files, key=os.path.getctime)
    
    print(f"{Fore.CYAN}=== Attendance Bunk Calculator ===\n")
    
    calculator = AttendanceCalculator(target_percentage=75.0, safety_buffer=1.0)
    
    if calculator.load_data(latest_file):
        # Get user input for future classes
        try:
            future = int(input("\nHow many more classes do you expect per subject this semester? (default 20): ") or "20")
        except ValueError:
            future = 20
        
        results = calculator.analyze_all_subjects(future_classes=future)
        calculator.get_overall_recommendation(results)
        
        print(f"\n{Fore.CYAN}{'='*70}")
        print(f"{Style.BRIGHT}Remember: This is a tool to help you plan, not an excuse to skip learning!")
        print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
