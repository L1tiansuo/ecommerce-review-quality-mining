"""独立训练/留出集，按清洗文本去重后划分；弱标签与人工金标需分开报告。"""
import argparse,sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'algo'))
import pandas as pd,joblib
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import classification_report
from core.preprocess import clean
def main(path):
    df=pd.read_csv(path).dropna(subset=['review','label']);df['text']=df.review.map(clean)
    df=df.drop_duplicates('text');df=df[df.text.str.len()>=5]
    # 删除相同正文的标签冲突样本。
    xtrain,xtest,ytrain,ytest=train_test_split(df.text,df.label.astype(int),test_size=1000,random_state=42,stratify=df.label)
    pipe=Pipeline([('tfidf',TfidfVectorizer(analyzer='char',ngram_range=(1,3),min_df=3,max_features=200000,sublinear_tf=True)),('svc',CalibratedClassifierCV(LinearSVC(C=1,class_weight='balanced',dual='auto'),cv=3))])
    pipe.fit(xtrain,ytrain);pred=pipe.predict(xtest)
    model=ROOT/'algo/models';model.mkdir(parents=True,exist_ok=True);joblib.dump(pipe,model/'sentiment.joblib',compress=3)
    out=ROOT/'data/eval';out.mkdir(parents=True,exist_ok=True)
    pd.DataFrame({'text':xtest,'label':ytest.map({1:'pos',0:'neg'})}).to_csv(out/'test_1000.csv',index=False,encoding='utf-8-sig')
    report={'dataset':'online_shopping_10_cats','split':'deduplicated text, stratified random holdout; source lacks product IDs, not a product-disjoint test','n_train':len(xtrain),'n_test':len(xtest),'binary':classification_report(ytest,pred,output_dict=True),'source_sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest()}
    (ROOT/'docs').mkdir(parents=True,exist_ok=True)
    (ROOT/'docs/training_metrics.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(report)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--csv',required=True);main(p.parse_args().csv)
