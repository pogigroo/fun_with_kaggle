# -*- coding: utf-8 -*-
# <nbformat>3.0</nbformat>

# <codecell>

import numpy as np
import scipy as sp
import pylab as pl
from sklearn.feature_extraction import text
from sklearn import feature_selection
from sklearn import svm
from sklearn import linear_model
from sklearn import neighbors
from sklearn import naive_bayes
from sklearn import metrics
from sklearn import cross_validation
from sklearn import grid_search
from sklearn import ensemble
from sklearn import decomposition
import csv, codecs, re, unicodedata
import simplenlp
from nltk import corpus
from nltk import tokenize
import nltk
from nltk import collocations
from nltk import stem
from time import time

# <codecell>

CHAT_WORDS = set([w.lower() for w in corpus.nps_chat.words()])
POS_KEY_WORDS = set(['maggot', 'pussy','dumb','bitch', 'momscreen','suffer','nazi',
     'shit','troll','rapist','bastard','hoe','buddy','idiot','dick','cuz','tard','breath','stupidity',
     'black','moron','racist', 'asshole','ass','shut','shitshut','complete','screen',
     'motherfucker','mom','crawl','fag','cunt','sound','knock','retard','plain',
     'coward','loser','lil','stupid','dirty','turd','cock','suck', 'fuck'])
STOP_WORDS = set([w.lower() for w in corpus.stopwords.words('english')])
CHAT_WO_STOP_WORDS = CHAT_WORDS - STOP_WORDS | set(['u','you','ur', 'are', 're'])

# <codecell>

## CONSTANTS and CONTROLS
TEST_RATIO = 0
SELECT_CHI2 = 1 # 0 or negative values to turn it off
FEATURE_EXTRACTION = 'raw' # possbile values 'raw' (non), 'pca', 'ica', 'l1-svc' (linear svc with l1 penalty)

# <codecell>

## function to load unicode CSV
def read_csv_columns(csv_file, columns, header = True):
    reader = csv.reader(codecs.open(csv_file, 'r', 'latin-1'), delimiter=',')
    if header:
        next(reader)
    data = []
    for row in reader:
        fields = []
        for c in columns:
            txt = re.sub(r'^"|"$','',row[c]).decode('unicode-escape')
            try:
                txt = txt.decode('unicode-escape')
            except: pass
            unicodedata.normalize('NFKD', txt).encode('ascii', 'ignore')
            fields.append(simplenlp.preprocess_text(txt))
        data.append(fields)
    return np.array(data)

def write_output(classifier, X, output_path = '../data/output.csv'):
    probas = classifier.predict_proba(X)
    with open(output_path, 'w') as f:
        f.write('Insult,\n')
        for i in xrange(probas.shape[0]):
            f.write(str(probas[i,1]))
            f.write(',\n')

# <codecell>

## load train and test data
train_data = read_csv_columns('../data/train.csv', columns = (0, 2))
test_data = read_csv_columns('../data/test_with_solutions.csv', columns= (0, 2))

# <codecell>

X = train_data[:, 1]
y = np.array(train_data[:, 0], dtype='uint8')
## 1. split the data into training and test
## train_X, test_X, train_y, test_y = cross_validation.train_test_split(X, y, test_size = TEST_RATIO, random_state = 0)
## 2. directly use the test.csv as test data
train_X, train_y = X, y
test_X, test_y = test_data[:, 1], np.array(test_data[:, 0], dtype='uint8')
## overfitting
#train_X, train_y = np.hstack((train_X, test_X)), np.hstack((train_y, test_y))

# <codecell>

######### nltk analysis ###########
train_pos_tweets, train_neg_tweets = train_X[train_y == 1], train_X[train_y == 0]
test_pos_tweets, test_neg_tweets = test_X[test_y == 1], test_X[test_y == 0]
## Bigram for positive tweets
train_pos_words = [w.lower() for w in tokenize.wordpunct_tokenize(' '.join(train_pos_tweets))]
word_filter = lambda w: len(w) < 3 or w in STOP_WORDS
pos_bicollocator = collocations.BigramCollocationFinder.from_words(train_pos_words)
pos_bicollocator.apply_word_filter(word_filter)
POS_BI_COLLACATIONS = pos_bicollocator.nbest(nltk.metrics.BigramAssocMeasures.likelihood_ratio, 100)
stemmer = stem.PorterStemmer()

# <codecell>

## find synonyms of a word
def synonyms(word):
    return [lemma.name for syn in corpus.wordnet.synsets(word) for lemma in syn.lemmas]

def my_tokenizer(txt):
    ## assert s.islower()
    ########### preprocessing  ############
    ## remove @name tag name - dont remove it, use it!
    #txt = re.compile(r'@\w+').sub('', txt)
    ## remove topics susch as #1
    txt = re.compile(r'(\A|\s)#[\w\d]+').sub("",txt)
    ## condense 3 or more than 3 letters into 1, e.g. hhhheeeello to hello
    txt = re.compile(r'(\w)\1{2,}').sub(r'\1', txt)
    feats = []
    ############ features based on raw text #############
    
    ############ features based on lower text ###########
    txt = txt.lower()
    nametags = re.findall(r'@\w+', txt)
    if nametags:
        feats += ['@NameTags']
    htmltags = re.findall(r'html', txt)
    if htmltags:
        feats += ['@HtmlTags']
    if any([w in txt for w in ['u', 'you', 'you are', 'ur']]):
        feats += ['@YouAre']
    ## has positive words
    if any([w in txt for w in POS_KEY_WORDS]):
        feats += ['@HasPositive']
    ## postive bi_collocations
    #for pair in POS_BI_COLLACATIONS:
    #    if all([w in txt for w in pair]):
    #        feats.append(pair)
    ############ features based on bag of words #########
    words = tokenize.wordpunct_tokenize(txt)
    ## stem words
    words = map(lambda w: stemmer.stem(w), words)
    ## bag of words
    #feats += filter(lambda t: t.isalpha() and t in CHAT_WORDS, words)
    feats += words
    ## has positive words
    ##if any([w in POS_KEY_WORDS for w in words]):
    ##    feats += ['@HasPositive']
    feats += [tuple(words[i:i+2]) for i in xrange(len(words)-1)]
    ## words after you, u, ur you're
    strict_words = filter(lambda w: w.isalpha() and w in CHAT_WO_STOP_WORDS, words)
    feats += [tuple(strict_words[i:i+2])
                for (i,w) in enumerate(strict_words) if w in ('you', 'u', 'ur')]
    feats += [tuple(strict_words[i:i+3])
                for (i,w) in enumerate(strict_words) if w in ('you', 'u', 'ur')]
    ## biwords of strict words
    feats += [(strict_words[i], strict_words[i+1]) for i in xrange(len(strict_words)-1)]
    ## synonyms of strict words
    #for sw in strict_words:
    #    if sw in POS_KEY_WORDS:
    #        feats += synonyms(w)
    for w in words:
        try:
            pos = corpus.wordnet.synsets(w)[0].pos
            if pos in ('n', 'a', 'v'):
                feats += [(w, pos)]
        except: pass
    return feats

## building features on training data
tfidf_vectorizer = text.TfidfVectorizer(charset = 'latin-1', lowercase=False, 
                                            sublinear_tf=True, tokenizer = my_tokenizer,#vocabulary = CHAT_WORDS,
                                            max_df=0.5)
print 'extracting tfidf from training set...'
t0 = time()
train_X = tfidf_vectorizer.fit_transform(train_X)
print 'done in %0.2fs' % (time() - t0)
print 'shape of training data', train_X.shape

# <codecell>

## add extra features to tfidf
'@HasPositive' in tfidf_vectorizer.get_feature_names()
#print filter(lambda f: f[0]=='you', tfidf_vectorizer.get_feature_names())

# <codecell>

## extract features from test data using same feature set
print 'extracting tfidf from testing set...'
t0 = time()
test_X = tfidf_vectorizer.transform(test_X)
print 'done in %0.2fs' % (time() - t0)
print 'shape of testing data', test_X.shape

# <codecell>

## optionally do feature selection based on chi2
if SELECT_CHI2 > 0:
    n_selected_features = int(train_X.shape[1] * SELECT_CHI2)
    print 'Extracting %d best features by a chi-squred test' % n_selected_features
    t0 = time()
    ch2 = feature_selection.SelectKBest(feature_selection.chi2, k = n_selected_features)
    train_X = ch2.fit_transform(train_X, train_y)
    test_X = ch2.transform(test_X)
    print 'done in %0.2fs' % (time() - t0)

# <codecell>

## optionally do feature extraction based on PCA or ICA
if FEATURE_EXTRACTION == 'raw':
    pass
elif FEATURE_EXTRACTION == 'pca':
    t0 = time()
    pca = decomposition.PCA(n_components=100)
    train_X = sp.sparse.coo_matrix(pca.fit_transform(train_X.todense()))
    test_X = sp.sparse.coo_matrix(pca.transform(test_X.todense()))
    print 'pca done in %0.3f' % (time() - t0)
elif FEATURE_EXTRACTION == 'ica':
    t0 = time()
    ica = decomposition.FastICA(n_components = 100)
    train_X = sp.sparse.coo_matrix(ica.fit_transform(train_X.todense()))
    test_X = sp.sparse.coo_matrix(ica.transform(test_X.todense()))
    print 'ica done in %0.3f' % (time() - t0)
elif FEATURE_EXTRACTION == 'l1-svc':
    t0 = time()
    l1svc = svm.LinearSVC(C = 1, penalty = 'l1', dual = False)
    l1svc.fit(train_X, train_y)
    train_X = l1svc.transform(train_X)
    test_X = l1svc.transform(test_X)
    print 'l1-svc feature selection done in %0.3f' % (time() - t0)
else:
    raise RuntimeError('unknown feature extraction method')

# <codecell>

## define feature names from tfidf vectorizer
tfidf_feature_names = tfidf_vectorizer.get_feature_names()
print train_X.shape, test_X.shape

# <codecell>

## benchmark classifiers
def benchmark(clf):
    print 76 * '_'
    print 'training: '
    print clf
    t0 = time()
    clf.fit(train_X, train_y)
    print 'training time: %0.2f' % (time() - t0)
    
    t0 = time()
    if hasattr(clf, 'predict_proba'):
        try:
            pred_probas = clf.predict_proba(test_X)[:,1]
        except:
            pred_probas = None
    else:
        pred_probas = None
    pred = clf.predict(test_X)
    print 'test time: %0.2f' % (time() - t0)
    
    print 'confusion matrix:'
    print metrics.confusion_matrix(test_y, pred)
    
    print 'classification rate:'
    print np.mean(test_y == pred) * 100., '%'
    
    if pred_probas is not None:
        fpr, tpr, thresholds = metrics.roc_curve(test_y, pred_probas)
        auc_area = metrics.auc(fpr, tpr)
        print 'AUC for test: ', auc_area
        print 'ROC plot'
        pl.figure()
        pl.plot(fpr, tpr, 'b-')
    
    misclassified_indices = (test_y != pred)
    misclassified = zip(test_data[misclassified_indices], test_y[misclassified_indices])
    return misclassified

# <codecell>

## test SVC
svc_classifier = svm.SVC(kernel = 'linear', C = 1, gamma = 0.01,  tol=0.001, probability = True)
#svc_classifier = svm.SVC(kernel = 'rbf', C = 10, gamma = 0.01,  tol=0.0001, probability = True)
misclassified = benchmark(svc_classifier)

# <codecell>

filter(lambda case: case[1] == 1, misclassified)

# <codecell>

## test naive bayesian bernoulli
nb_bernoulli_classifier = naive_bayes.BernoulliNB(alpha = 0.4, fit_prior=True)
misclassified = benchmark(nb_bernoulli_classifier)
#negative_features_indices = np.argsort(nb_bernoulli_classifier.feature_log_prob_[0,:])[-30:]
#negative_features = [tfidf_feature_names[i] for i in negative_features_indices]
#print 'negative features...'
#print negative_features
#positive_features_indices = np.argsort(nb_bernoulli_classifier.feature_log_prob_[1,:])[-50:]
#positive_features = [tfidf_feature_names[i] for i in positive_features_indices]
#print 'positive features...'
#print positive_features

# <codecell>

### classification by voting ####
class BiVotingClassifier:
    def __init__(self, model1, model2):
        self.model1 = model1
        self.model2 = model2
    def fit(self, X, y):
        self.model1.fit(X, y)
        self.model2.fit(X, y)
    def predict(self, X):
        proba = self.predict_proba(X)
        return np.argmax(proba, axis = 1)
    def predict_proba(self, X):
        proba1 = self.model1.predict_proba(X)
        proba2 = self.model2.predict_proba(X)
        n_samples, n_labels = proba1.shape
        assert n_labels == 2
        proba = np.zeros((n_samples, n_labels))
        for i in xrange(n_samples):
            proba[i, 0] = max(proba1[i, 0], proba2[i, 0])
            proba[i, 1] = max(proba1[i, 1], proba2[i, 1])
            proba[i, ] /= sum(proba[i, ])
            """
            if np.max(proba1[i,:]) > np.max(proba2[i,:]):
                proba[i, :] = proba1[i, :]
            else:
                proba[i, :] = proba2[i, :]
            """
        return proba
    
#bivoting = BiVotingClassifier(svm.SVC(kernel = 'rbf', C = 10, gamma = 0.01,  tol=0.0001, probability = True), 
bivoting = BiVotingClassifier(svm.SVC(kernel = 'linear', C = 1, gamma = 0.01,  tol=0.0001, probability = True), 
                                naive_bayes.BernoulliNB(alpha = 0.4, fit_prior=True))
misclassified = benchmark(bivoting)

# <codecell>

write_output(bivoting, test_X)
print 'writing done...'

# <codecell>

## test SGD with Elastic Net penalty
sgdc_classifier = linear_model.SGDClassifier(alpha = 0.0001, n_iter = 200, penalty = 'l2')
misclassified = benchmark(sgdc_classifier)

# <codecell>

## test ensemble random trees
forest_classifier = ensemble.RandomForestClassifier(n_estimators=60, n_jobs = -1)
train_X_sparse, test_X_sparse = train_X, test_X
train_X, test_X = train_X.todense(), test_X.todense()
misclassified = benchmark(forest_classifier)
train_X, test_X = train_X_sparse, test_X_sparse

# <codecell>

## test ensemble extremely randomized tree
random_forest_classifier = ensemble.ExtraTreesClassifier(n_estimators = 100, n_jobs = -1)
train_X_sparse, test_X_sparse = train_X, test_X
train_X, test_X = train_X.todense(), test_X.todense()
misclassified = benchmark(random_forest_classifier)
train_X, test_X = train_X_sparse, test_X_sparse

# <codecell>

## test ensemble GradientBoostingClassifier
boosting_classifier = ensemble.GradientBoostingClassifier(n_estimators = 200, max_depth = 1, learn_rate = 0.1)
train_X_sparse, test_X_sparse = train_X, test_X
train_X, test_X = train_X.todense(), test_X.todense()
misclassified = benchmark(boosting_classifier)
train_X, test_X = train_X_sparse, test_X_sparse

# <codecell>

## test ridge classifier
ridge_classifier = linear_model.RidgeClassifier(tol = 1e-1)
benchmark(ridge_classifier)

# <codecell>

## test linear SVC
linear_svc_classifier = svm.LinearSVC(loss = 'l2', penalty = 'l1', dual = False, tol = 1e-3)
benchmark(linear_svc_classifier)

# <codecell>

## do a grid search on meta-pararmeters of SVC
cv_svc_classifier = grid_search.GridSearchCV(svm.SVC(probability = True), 
       dict(
                kernel = ('rbf','linear'),
                C = (1, 10, 100, 1000),
                gamma = (0.01, 0.1, 1),
        ), 
        n_jobs = -1
)
cv_svc_classifier.fit(train_X, train_y)
print cv_svc_classifier.best_estimator_
## SVC(C=10, cache_size=200, class_weight=None, coef0=0.0, degree=3, gamma=0.1,
##  kernel=rbf, probability=False, shrinking=True, tol=0.001, verbose=False)
misclassified = benchmark(cv_svc_classifier.best_estimator_)

# <codecell>

## test naive bayesian multinomial
nb_multinomial_classifier = naive_bayes.MultinomialNB(alpha = 0.4)
misclassified = benchmark(nb_multinomial_classifier)

# <codecell>


