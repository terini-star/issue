import re
import urllib.request
import ssl
import feedparser
from collections import Counter
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.tag import pos_tag
from nltk.chunk import ne_chunk
from nltk.tree import Tree

# English Stopwords
ENG_STOPWORDS = set([
    'say', 'says', 'said', 'will', 'new', 'us', 'u.s.', 'u.s', 'first', 'two', 'one', 
    'year', 'years', 'after', 'with', 'over', 'against', 'world', 'news', 'people', 
    'report', 'reports', 'reporter', 'google', 'rss', 'time', 'times', 'today', 
    'show', 'shows', 'day', 'days', 'make', 'makes', 'made', 'get', 'gets', 'got', 
    'go', 'goes', 'went', 'back', 'take', 'takes', 'took', 'see', 'sees', 'saw',
    'could', 'would', 'should', 'also', 'many', 'more', 'most', 'some', 'other', 
    'another', 'here', 'there', 'who', 'what', 'where', 'when', 'why', 'how'
])

# Korean Stopwords
KOR_STOPWORDS = set([
    '뉴스', '오늘', '내일', '올해', '지난', '대해', '위해', '때문', '통해', '이번', 
    '최근', '관련', '기자', '보도', '우려', '분석', '상황', '이유', '하루', '하루종일',
    '일부', '대부분', '가운데', '시간', '오후', '오전', '최대', '최소', '이후', '이전',
    '정도', '사실', '내용', '진행', '발표', '확인', '예정', '시작', '결과', '기록',
    '전망', '계획', '종합', '단독', '속보', '주요', '최초', '연합뉴스', '뉴시스', 'ytn',
    'sbs', 'kbs', 'mbc', 'jtbc', '조선일보', '중앙일보', '동아일보', '한겨레', '경향신문'
])

# Korean Grammatical Particles (조사) sorted by length descending for greedy match
KOR_PARTICLES = [
    '으로부터', '에서는', '에게서', '으로서', '으로써', '하고는', '조차도',
    '에서', '에게', '한테', '까지', '부터', '으로', '와과', '하고', '이며',
    '은', '는', '이', '가', '을', '를', '의', '에', '로', '와', '과', '도', '만', 
    '뿐', '든', '나', '고', '라', '며'
]

# Korean common verbal endings/suffixes to strip
KOR_VERBAL_SUFFIXES = [
    '했습니다', '합니다', '했다', '한다', '한다며', '했다며', '했으며', '하며', 
    '하는', '할', '한', '하', '됩니다', '된다', '되고', '된', '될', '됨', '되',
    '있습니다', '있다', '있고', '있는', '있을', '있음', '있',
    '않습니다', '않는다', '않고', '않는', '않을', '않음', '않',
    '적', '화', '성', '적', '들'
]

def clean_korean_word(word):
    """
    Cleans a Korean word by removing punctuation, stripping grammatical particles (조사),
    and common verbal suffixes, leaving the core noun root.
    """
    # Remove any non-alphanumeric and non-Korean characters
    word = re.sub(r'[^가-힣a-zA-Z0-9]', '', word)
    if len(word) < 2:
        return ""
        
    # Greedy strip particles
    stripped = True
    while stripped:
        stripped = False
        # 1. Strip grammatical particles
        for particle in KOR_PARTICLES:
            if word.endswith(particle) and len(word) - len(particle) >= 2:
                word = word[:-len(particle)]
                stripped = True
                break
        
        # 2. Strip verbal suffixes
        for suffix in KOR_VERBAL_SUFFIXES:
            if word.endswith(suffix) and len(word) - len(suffix) >= 2:
                word = word[:-len(suffix)]
                stripped = True
                break
                
    return word if len(word) >= 2 else ""

def extract_english_entities(titles_with_articles):
    """
    Extracts English entities (PERSON, ORGANIZATION, GPE) and relevant nouns using NLTK.
    """
    keywords = []
    # Cache stop words
    stop_words = set(stopwords.words('english')).union(ENG_STOPWORDS)
    
    # Store items for each word to map back to original articles
    word_to_articles = {}
    word_categories = {}
    
    def add_keyword(word, category, article):
        # Normalize title casing (e.g. Trump, Biden, Ukraine)
        norm_word = word.title() if len(word) > 3 else word
        
        # Avoid single letters or digits only
        if not re.match(r'^[a-zA-Z\s]+$', norm_word) or norm_word.lower() in stop_words:
            return
            
        keywords.append(norm_word)
        
        # Save category (prefer entity types over plain Noun)
        if norm_word not in word_categories or word_categories[norm_word] == 'NOUN':
            word_categories[norm_word] = category
            
        if norm_word not in word_to_articles:
            word_to_articles[norm_word] = []
        if article not in word_to_articles[norm_word]:
            word_to_articles[norm_word].append(article)

    def process_node(node, article):
        if isinstance(node, Tree):
            # This is a named entity (e.g., PERSON, GPE, ORGANIZATION)
            entity_label = node.label()
            entity_name = " ".join([token for token, pos in node.leaves()])
            
            # Check length and characters
            entity_name_clean = re.sub(r'[^a-zA-Z0-9\s]', '', entity_name).strip()
            if len(entity_name_clean) >= 3 and entity_name_clean.lower() not in stop_words:
                # Map entities to standard naming
                cat = 'NOUN'
                if entity_label in ['PERSON', 'PEOPLE']:
                    cat = 'PERSON'
                elif entity_label in ['ORGANIZATION', 'ORGANISATION']:
                    cat = 'ORGANIZATION'
                elif entity_label in ['GPE', 'LOCATION']:
                    cat = 'LOCATION'
                    
                add_keyword(entity_name_clean, cat, article)
        else:
            # Leaf node: POS tagged word
            word, pos = node
            word_clean = re.sub(r'[^a-zA-Z]', '', word).strip()
            # We want nouns (NN, NNP, NNS, NNPS)
            if (pos.startswith('NN') and 
                len(word_clean) >= 3 and 
                word_clean.lower() not in stop_words):
                
                cat = 'LOCATION' if pos == 'NNP' and word_clean.isupper() else 'NOUN'
                add_keyword(word_clean, cat, article)

    for article in titles_with_articles:
        title = article['title']
        # Clean title text from common news prefixes/suffixes like " - Reuters" or " - Google News"
        title_clean = re.sub(r'\s-\s.*$', '', title)
        
        try:
            tokens = word_tokenize(title_clean)
            tagged = pos_tag(tokens)
            tree = ne_chunk(tagged)
        except Exception as e:
            # Fallback if NLTK taggers fail (e.g., resources missing or download issue)
            tokens = re.findall(r'\b[a-zA-Z]{3,}\b', title_clean)
            tree = [(t, 'NN') for t in tokens]

        # Process the NLTK Parse Tree
        if isinstance(tree, Tree):
            for child in tree:
                process_node(child, article)
        else:
            for item in tree:
                process_node(item, article)
                
    # Count frequency
    counts = Counter(keywords)
    
    # Format result
    result = []
    for word, count in counts.most_common(40):
        # Filter out noise
        if len(word_to_articles.get(word, [])) == 0:
            continue
        result.append({
            'word': word,
            'count': count,
            'category': word_categories.get(word, 'NOUN'),
            'articles': word_to_articles[word][:6] # Limit articles for payload size
        })
        
    return result

def extract_korean_entities(titles_with_articles):
    """
    Extracts Korean keywords by parsing titles, stripping particles, 
    and filtering out stopwords.
    """
    keywords = []
    word_to_articles = {}
    word_categories = {}
    
    def add_keyword(word, category, article):
        keywords.append(word)
        
        # Save category
        if word not in word_categories or word_categories[word] == 'NOUN':
            word_categories[word] = category
            
        if word not in word_to_articles:
            word_to_articles[word] = []
        if article not in word_to_articles[word]:
            word_to_articles[word].append(article)
            
    # Custom rule for basic Korean entity detection based on capitalization (for mixed English/Korean)
    # or known entity prefixes/suffixes.
    for article in titles_with_articles:
        title = article['title']
        title_clean = re.sub(r'\s-\s.*$', '', title) # Remove source info
        
        # Tokenize by space
        tokens = title_clean.split()
        for token in tokens:
            # Check if token contains Korean
            if re.search(r'[가-힣]', token):
                cleaned = clean_korean_word(token)
                if cleaned and cleaned not in KOR_STOPWORDS:
                    # Categorization heuristic:
                    # If it ends with 국 (country), 시 (city), 도 (province), GPE/Location
                    cat = 'NOUN'
                    if cleaned.endswith(('국', '시', '현', '주', '강원도', '경기도', '충청도', '경상도', '전라도', '제주도')) and len(cleaned) >= 2:
                        cat = 'LOCATION'
                    elif cleaned.endswith(('사', '그룹', '협회', '부', '원', '청', '당', '위원회', '연구소')) and len(cleaned) >= 3:
                        cat = 'ORGANIZATION'
                    elif cleaned.endswith(('대통령', '의원', '장관', '감독', '선수', '작가', '대표', '씨')) and len(cleaned) >= 3:
                        cat = 'PERSON'
                    
                    add_keyword(cleaned, cat, article)
            else:
                # English word inside Korean title (e.g. Apple, ChatGPT)
                cleaned = re.sub(r'[^a-zA-Z0-9]', '', token)
                if len(cleaned) >= 3 and cleaned.lower() not in ENG_STOPWORDS:
                    cat = 'NOUN'
                    if cleaned.isupper():
                        cat = 'ORGANIZATION'
                    elif cleaned[0].isupper():
                        cat = 'LOCATION'
                    add_keyword(cleaned, cat, article)
                
    counts = Counter(keywords)
    
    result = []
    for word, count in counts.most_common(40):
        if len(word_to_articles.get(word, [])) == 0:
            continue
        result.append({
            'word': word,
            'count': count,
            'category': word_categories.get(word, 'NOUN'),
            'articles': word_to_articles[word][:6]
        })
        
    return result

def fetch_rss_feed(url):
    """
    Fetches the RSS feed content using urllib and bypasses security blocks with SSL context.
    """
    # Bypass SSL verification
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, context=ctx) as response:
        html = response.read()
        
    feed = feedparser.parse(html)
    articles = []
    
    for entry in feed.entries:
        articles.append({
            'title': entry.get('title', ''),
            'link': entry.get('link', ''),
            'source': entry.get('source', {}).get('value', 'Google News'),
            'published': entry.get('published', '')
        })
    return articles

def get_trends(lang='en'):
    """
    Main function to fetch RSS feeds and extract trends for 'en' or 'ko'.
    """
    if lang == 'ko':
        url = "https://news.google.com/rss?hl=ko&gl=KR&ceid=KR:ko"
        articles = fetch_rss_feed(url)
        return extract_korean_entities(articles)
    else:
        url = "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"
        articles = fetch_rss_feed(url)
        return extract_english_entities(articles)

if __name__ == '__main__':
    # Download NLTK resources if run directly
    nltk.download('punkt')
    nltk.download('averaged_perceptron_tagger')
    nltk.download('maxent_ne_chunker')
    nltk.download('words')
    nltk.download('stopwords')
    
    print("Testing English trends extraction...")
    en_trends = get_trends('en')
    for idx, trend in enumerate(en_trends[:10]):
        print(f"{idx+1}. {trend['word']} ({trend['category']}): {trend['count']} mentions. Example article: {trend['articles'][0]['title']}")
        
    print("\nTesting Korean trends extraction...")
    ko_trends = get_trends('ko')
    for idx, trend in enumerate(ko_trends[:10]):
         print(f"{idx+1}. {trend['word']} ({trend['category']}): {trend['count']} mentions. Example article: {trend['articles'][0]['title']}")
