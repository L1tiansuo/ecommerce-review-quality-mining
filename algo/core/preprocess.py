"""所有入库文本先脱敏。raw 表示清洗前文本，不表示保留个人信息。"""
import re, html
def mask(text):
    text=str(text or '')
    for pattern in [r'(?<!\d)1[3-9]\d{9}(?!\d)',r'(?<!\d)\d{17}[\dXx](?!\d)',r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}']:
        text=re.sub(pattern,'[已脱敏]',text)
    return text
def clean(text):
    return re.sub(r'\s+',' ',re.sub(r'<[^>]+>','',html.unescape(mask(text)))).strip()
