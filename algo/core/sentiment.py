"""可替换的情感推理器。模型缺失时明确返回 rule-baseline 与 degraded。"""
from pathlib import Path
import re, joblib
MODEL=Path(__file__).resolve().parents[1]/'models/sentiment.joblib'
POS='好 很好 满意 不错 喜欢 优秀 完美 清晰 耐用 划算 便宜 漂亮 精美 推荐 赞 值得 快 牢固 丰富 方便'.split()
NEG='差 糟糕 垃圾 失望 坏 破损 压坏 开胶 掉漆 掉线 断连 卡顿 死机 虚标 慢 贵 推诿 不回复 后悔 不行 问题 故障 难用'.split()
NEGATIONS=('不是','毫无','没有','不','没','无','未','别','谈不上')
_model=None
def local_score(text):
    """按情感词前缀处理否定，避免对含“不”的整句无条件翻转。"""
    score=0
    # 长词优先防止“不好/很好”等子串重复计分。
    occupied=set()
    for word,sign in sorted([(w,1) for w in POS]+[(w,-1) for w in NEG],key=lambda p:-len(p[0])):
        for m in re.finditer(re.escape(word),text):
            if any(i in occupied for i in range(m.start(),m.end())):continue
            prefix=text[max(0,m.start()-4):m.start()]
            inverse=sum(prefix.count(n) for n in ('不','没','无','未'))%2
            v=sign*(-1 if inverse else 1)
            if any(x in prefix for x in ('非常','特别','极其','太')):v*=1.5
            if any(x in prefix for x in ('有点','稍微','略')):v*=.6
            score+=v;occupied.update(range(m.start(),m.end()))
    return max(-1.,min(1.,score*.65))
def version():return 'tfidf-svc-v1' if MODEL.exists() else 'rule-baseline-v1'
def predict(texts):
    global _model
    if MODEL.exists():
        if _model is None:_model=joblib.load(MODEL)
        probabilities=_model.predict_proba(texts)
        classes=list(_model.classes_);idx=classes.index(1)
        return [{'label':'pos' if p[idx]>.6 else 'neg' if p[idx]<.4 else 'neu','confidence':round(float(max(p)),4),'score':round(float(2*p[idx]-1),4)} for p in probabilities]
    return [{'label':'pos' if (s:=local_score(t))>.2 else 'neg' if s<-.2 else 'neu','confidence':round(.5+abs(s)*.45,4),'score':s} for t in texts]
