"""Aho-Corasick 多模式匹配，窗口情感与句内特性去重。词表可由请求快照覆盖。"""
import json,re
from pathlib import Path
import ahocorasick
from .sentiment import local_score
DICT_PATH=Path(__file__).resolve().parents[1]/'data/aspect_dict.json'
DEFAULT=json.loads(DICT_PATH.read_text(encoding='utf-8'))
def extract(text,dictionary=None):
    dictionary=dictionary or DEFAULT
    ac=ahocorasick.Automaton()
    for d in dictionary['dimensions']:
        for f in d['features']:
            for word in f['synonyms']:ac.add_word(word,(word,f['code'],d['code']))
    ac.make_automaton();hits={}
    for end,(word,feature,dim) in ac.iter(text):
        start=end-len(word)+1
        # 窗口不跨越标点，降低相邻方面的情感串扰。
        left=max([text.rfind(p,0,start) for p in '，。！？；,!?;']+[-1])+1
        rights=[i for p in '，。！？；,!?;' if (i:=text.find(p,end+1))>=0]
        right=min(rights) if rights else len(text)
        window=text[max(left,start-12):min(right,end+13)]
        strength=local_score(window)
        key=(left,feature)
        item={'word':word,'feature_code':feature,'dimension':dim,'polarity':1 if strength>.2 else -1 if strength<-.2 else 0,'strength':strength,'start':start,'end':end+1}
        if key not in hits or abs(strength)>abs(hits[key]['strength']):hits[key]=item
    return sorted(hits.values(),key=lambda a:a['start'])
