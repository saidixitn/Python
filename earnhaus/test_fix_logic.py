import re
from bs4 import BeautifulSoup

# Case 1: Bad job 6adf3a1192132b036d3e9b8d snippet
snippet1 = """<p><strong>Speech-Language Pathologist</strong></p><p><strong>Letort Spring Nursing and Rehabhas an exciting opportunity for a Speech-Language Pathologist (SLP)to join our team</strong></p><ul><li><strong><strong>Competitive pay</strong>.</li><li><strong><strong>Comprehensive benefits packagefor full-time employees.</strong></li><li><strong>consistent PRN also available</li></ul><p>We're looking for a dedicated and compassionate SLP to join our in-house rehabilitation team and provide high-quality, person-centered care to our residents and patients.</p>"""

# Case 2: Request #7 snippet
snippet2 = """<p><strong>Occupational Therapy Assistant Full-Time</strong></p><strong>St. Patrick's Manor Nursing & Rosarie Centerhas an exciting opportunity for aFull-Time Occupational Therapy Assistant (OTA)We are looking for a dedicated OTA to join our in-house rehabilitation team of outstanding professionals who provide person-centered care to our residents and patients. Our goal is to help each individual achieve meaningful outcomes while maintaining the highest standards of quality and compassion.<p>AtSt. Patrick's Manor Nursing & Rosarie Center, our clinical teams are committed to providing individualized care with compassion, collaboration, and excellence.</p>"""

def fix_html_tags(html_str):
    # Let's fix duplicated strongs: <strong><strong> -> <strong>
    fixed = re.sub(r'<strong>\s*<strong>', '<strong>', html_str, flags=re.I)
    
    # Fix <li><strong>text</li> where </strong> is missing before </li>
    fixed = re.sub(r'(<li>\s*<strong>)(.*?)(</li>)', lambda m: m.group(1) + m.group(2) + ('</strong>' if '</strong>' not in m.group(2) else '') + m.group(3), fixed, flags=re.I | re.DOTALL)
    
    # In Case 2: </p><strong>Facility has an exciting...<p>
    # Notice: <strong>Facility has an exciting opportunity for a ... (OTA)We are looking...
    # The strong tag should only wrap the facility headline, or if unclosed before <p>, close it!
    # Wait, in standard QRM jobs, what should be bold in the intro?
    # Let's check how the fine job does it!
    return fixed

print("Testing snippet 1:")
soup1 = BeautifulSoup(snippet1, 'html.parser')
print("BeautifulSoup default parsing:")
print(str(soup1))
