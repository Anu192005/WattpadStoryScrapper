import os
import re
import sys
import json
import time
import random
import requests
from bs4 import BeautifulSoup

# Reconfigure stdout to use UTF-8
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

class WattpadScraper:
    def __init__(self, delay_min=1.5, delay_max=2.5):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
        }
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def fetch_story_metadata(self, story_url):
        """
        Fetches the story landing page and extracts the metadata and table of contents
        from Remix's window.__remixContext payload.
        """
        print(f"Fetching story page: {story_url}")
        try:
            response = self.session.get(story_url, timeout=15)
            if response.status_code != 200:
                raise Exception(f"Failed to fetch story page. Status code: {response.status_code}")
        except Exception as e:
            raise Exception(f"Network error while fetching story landing page: {e}")

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the remix context script
        remix_script = None
        for s in soup.find_all('script'):
            if s.string and 'window.__remixContext =' in s.string:
                remix_script = s.string
                break

        if not remix_script:
            raise Exception("Could not find story metadata in page (remix context missing). Wattpad may have updated its page structure.")

        # Extract the JSON block
        start_idx = remix_script.find('{')
        end_idx = remix_script.rfind('}')
        if start_idx == -1 or end_idx == -1:
            raise Exception("Failed to find JSON boundaries in remix context script.")
        
        json_str = remix_script[start_idx:end_idx+1]
        try:
            context_data = json.loads(json_str)
        except Exception as e:
            raise Exception(f"Failed to parse remix context JSON: {e}")

        loader_data = context_data.get('state', {}).get('loaderData', {})
        story_data = None
        
        # Search dynamically for the story route key (usually routes/story.$storyid)
        for key, val in loader_data.items():
            if key.startswith('routes/story.') and val and 'story' in val:
                story_data = val['story']
                break

        if not story_data:
            raise Exception("Could not locate the story object inside the loader data payload.")

        # Extract and clean metadata
        metadata = {
            'id': story_data.get('id'),
            'title': story_data.get('title', 'Untitled').strip(),
            'author': story_data.get('user', {}).get('name', 'Unknown').strip(),
            'author_username': story_data.get('user', {}).get('username', 'Unknown').strip(),
            'description': story_data.get('description', '').strip(),
            'cover_url': story_data.get('cover', ''),
            'completed': story_data.get('completed', False),
            'categories': story_data.get('categories', []),
            'tags': story_data.get('tags', []),
            'chapters': []
        }

        # Clean description HTML tags if any
        if metadata['description']:
            desc_soup = BeautifulSoup(metadata['description'], 'html.parser')
            metadata['description'] = desc_soup.get_text('\n')

        # Extract chapters (parts)
        parts = story_data.get('parts', [])
        for part in parts:
            if not part.get('draft', False):  # Skip drafts
                metadata['chapters'].append({
                    'id': part.get('id'),
                    'title': part.get('title', f"Chapter {part.get('id')}").strip(),
                    'url': part.get('url', '')
                })

        return metadata

    def fetch_chapter_html(self, chapter_id):
        """
        Fetches the raw story text HTML for a chapter via the apiv2 endpoint.
        """
        url = f"https://www.wattpad.com/apiv2/storytext?id={chapter_id}"
        try:
            response = self.session.get(url, timeout=15)
            if response.status_code != 200:
                raise Exception(f"Failed to fetch chapter ID {chapter_id}. Status: {response.status_code}")
            return response.text
        except Exception as e:
            raise Exception(f"Network error while fetching chapter {chapter_id}: {e}")

    def clean_chapter_text(self, html_content):
        """
        Cleans the chapter HTML and converts it into three target formats:
        1. Plain Text: Line breaks and normal spacing.
        2. Markdown: Formatted bold/italics.
        3. XHTML: Formatted XML-compliant markup for EPUB.
        """
        soup = BeautifulSoup(html_content, 'html.parser')

        # --- Generate Plain Text ---
        paragraphs = []
        for p in soup.find_all('p'):
            text = p.get_text(strip=True)
            if text:
                paragraphs.append(text)
        plain_text = "\n\n".join(paragraphs)

        # --- Generate Markdown ---
        md_paragraphs = []
        for p in soup.find_all('p'):
            p_soup = BeautifulSoup(str(p), 'html.parser')
            # Handle inline styling inside BS
            for em in p_soup.find_all(['em', 'i']):
                em.replace_with(f"*{em.get_text()}*")
            for strong in p_soup.find_all(['strong', 'b']):
                strong.replace_with(f"**{strong.get_text()}**")
            
            p_text = p_soup.get_text(strip=True)
            # Basic escape of markdown characters if needed, but keep it readable
            if p_text:
                md_paragraphs.append(p_text)
        markdown = "\n\n".join(md_paragraphs)

        # --- Generate XHTML (EPUB-compatible) ---
        # Ensure all tags are closed properly, remove unallowed tags
        xhtml_paragraphs = []
        for p in soup.find_all('p'):
            # Convert inner contents to a clean HTML fragment
            cleaned_p_html = ""
            for child in p.children:
                if child.name in ['em', 'i']:
                    cleaned_p_html += f"<em>{child.get_text()}</em>"
                elif child.name in ['strong', 'b']:
                    cleaned_p_html += f"<strong>{child.get_text()}</strong>"
                elif child.name == 'br':
                    cleaned_p_html += "<br/>"
                else:
                    cleaned_p_html += child.get_text() if not child.name else child.get_text()
            
            cleaned_p_html = cleaned_p_html.strip()
            if cleaned_p_html:
                # Wrap in XHTML valid <p>
                xhtml_paragraphs.append(f"<p>{cleaned_p_html}</p>")
        xhtml = "\n".join(xhtml_paragraphs)

        return {
            'text': plain_text,
            'markdown': markdown,
            'xhtml': xhtml
        }

    def sleep_random(self):
        """Sleep for a random duration between self.delay_min and self.delay_max"""
        sleep_time = random.uniform(self.delay_min, self.delay_max)
        time.sleep(sleep_time)

    def fetch_stories_by_genre_or_tag(self, search_type, query_val, max_results=100, delay_min=1.0, delay_max=2.0, progress_callback=None):
        """
        Fetches stories by category (genre) or tag.
        search_type: "Genre" or "Tag"
        query_val: category ID (int/str) or tag name (str)
        max_results: max stories to return
        progress_callback: optional function taking (current_count, status_message)
        """
        import urllib.parse
        
        stories = []
        offset = 0
        limit = min(100, max_results)
        
        if "Genre" in search_type:
            base_url = f"https://api.wattpad.com/v4/stories?category={query_val}&limit={limit}"
        else:
            tag_str = str(query_val).strip()
            encoded_tag = urllib.parse.quote(tag_str)
            base_url = f"https://api.wattpad.com/v4/stories?tag={encoded_tag}&limit={limit}"
            
        while len(stories) < max_results:
            url = f"{base_url}&offset={offset}"
            if progress_callback:
                progress_callback(len(stories), f"Fetching stories starting at offset {offset}...")
                
            try:
                response = self.session.get(url, timeout=15)
                if response.status_code != 200:
                    print(f"Error fetching from offset {offset}: HTTP status {response.status_code}")
                    break
                data = response.json()
            except Exception as e:
                print(f"Network error at offset {offset}: {e}")
                break
                
            batch = data.get('stories', [])
            if not batch:
                break
                
            stories.extend(batch)
            offset += len(batch)
            
            if len(batch) < limit or len(stories) >= max_results:
                break
                
            time.sleep(random.uniform(delay_min, delay_max))
            
        return stories[:max_results]


def classify_english_group_and_profile(categories, tags):
    """
    Classifies a story into one of the 8 English Ambassador Groups and its specific Profile/Genre.
    """
    # Mapping of Category IDs
    cat_to_info = {
        14: ("English - Group 1", "Action"),
        11: ("English - Group 1", "Adventure"),
        8: ("English - Group 1", "Mystery / Thriller"),
        23: ("English - Group 1", "Historical Fiction"),
        
        9: ("English - Group 2", "Horror (Fright)"),
        12: ("English - Group 2", "Paranormal"),
        22: ("English - Group 2", "Werewolf"),
        18: ("English - Group 2", "Vampire"),
        
        6: ("English - Group 3", "Fanfiction (Fanfic)"),
        
        5: ("English - Group 4", "Science Fiction"),
        3: ("English - Group 4", "Fantasy"),
        
        4: ("English - Group 5", "Romance"),
        
        1: ("English - Group 6", "Teen Fiction (Teen Fic)"),
        7: ("English - Group 6", "Humor"),
        24: ("English - Group 6", "ChickLit"),
        
        2: ("English - Group 7", "Poetry"),
        17: ("English - Group 7", "Short Story"),
        
        16: ("English - Group 8", "Non-Fiction"),
    }
    
    # Check category IDs first
    for cat in categories:
        if isinstance(cat, int) and cat in cat_to_info:
            return cat_to_info[cat]
            
    # Check tag names/keywords if category ID was not mapped
    tag_keywords = [
        # Group 1
        ("action", "English - Group 1", "Action"),
        ("adventure", "English - Group 1", "Adventure"),
        ("mystery", "English - Group 1", "Mystery / Thriller"),
        ("thriller", "English - Group 1", "Mystery / Thriller"),
        ("historical", "English - Group 1", "Historical Fiction"),
        ("history", "English - Group 1", "Historical Fiction"),
        # Group 2
        ("horror", "English - Group 2", "Horror (Fright)"),
        ("fright", "English - Group 2", "Horror (Fright)"),
        ("paranormal", "English - Group 2", "Paranormal"),
        ("werewolf", "English - Group 2", "Werewolf"),
        ("werewolves", "English - Group 2", "Werewolf"),
        ("vampire", "English - Group 2", "Vampire"),
        ("vampires", "English - Group 2", "Vampire"),
        # Group 3
        ("fanfic", "English - Group 3", "Fanfiction (Fanfic)"),
        ("fanfiction", "English - Group 3", "Fanfiction (Fanfic)"),
        ("fandom", "English - Group 3", "Fandoms"),
        ("fandoms", "English - Group 3", "Fandoms"),
        # Group 4
        ("scifi", "English - Group 4", "Science Fiction"),
        ("sciencefiction", "English - Group 4", "Science Fiction"),
        ("science-fiction", "English - Group 4", "Science Fiction"),
        ("fantasy", "English - Group 4", "Fantasy"),
        # Group 5
        ("romance", "English - Group 5", "Romance"),
        ("love", "English - Group 5", "Romance"),
        ("lgbt", "English - Group 5", "LGBTQ+"),
        ("lgbtq", "English - Group 5", "LGBTQ+"),
        ("lgbtq+", "English - Group 5", "LGBTQ+"),
        ("lgbtqplus", "English - Group 5", "LGBTQ+"),
        ("afterdark", "English - Group 5", "After Dark"),
        ("after-dark", "English - Group 5", "After Dark"),
        ("after dark", "English - Group 5", "After Dark"),
        # Group 6
        ("teen", "English - Group 6", "Teen Fiction (Teen Fic)"),
        ("teenfic", "English - Group 6", "Teen Fiction (Teen Fic)"),
        ("teenfiction", "English - Group 6", "Teen Fiction (Teen Fic)"),
        ("humor", "English - Group 6", "Humor"),
        ("chicklit", "English - Group 6", "ChickLit"),
        ("chick-lit", "English - Group 6", "ChickLit"),
        # Group 7
        ("poetry", "English - Group 7", "Poetry"),
        ("poem", "English - Group 7", "Poetry"),
        ("poems", "English - Group 7", "Poetry"),
        ("shortstory", "English - Group 7", "Short Story"),
        ("shortstories", "English - Group 7", "Short Story"),
        ("short-story", "English - Group 7", "Short Story"),
        # Group 8
        ("nonfiction", "English - Group 8", "Non-Fiction"),
        ("non-fiction", "English - Group 8", "Non-Fiction"),
        ("identity", "English - Group 8", "Identity and Culture"),
        ("culture", "English - Group 8", "Identity and Culture"),
        ("socialthemes", "English - Group 8", "Social Themes"),
        ("social-themes", "English - Group 8", "Social Themes"),
        ("social themes", "English - Group 8", "Social Themes"),
    ]
    
    tags_lower = [t.lower() for t in tags]
    for tag in tags_lower:
        for keyword, group, profile in tag_keywords:
            if keyword in tag:
                return group, profile
                
    # Fallback to category text mapping if still not resolved
    for cat in categories:
        if isinstance(cat, str):
            cat_lower = cat.lower()
            for keyword, group, profile in tag_keywords:
                if keyword in cat_lower:
                    return group, profile
                    
    return "Unknown", "Unknown"


def classify_series_status(title, description):
    """
    Heuristically classifies a story's series status based on title and description.
    Options: 'yes first in series', 'no', 'yes but can be read as standalone'
    """
    title_lower = title.lower() if title else ""
    desc_lower = description.lower() if description else ""
    
    # 1. Standalone check
    if "standalone" in title_lower or "standalone" in desc_lower:
        return "yes but can be read as standalone"
        
    # 2. First in series check
    first_in_series_indicators = [
        "book 1", "book one", "vol 1", "volume 1", "part 1", "book #1", "bk 1", 
        "bkone", "first book", "book 1 of", "book one of"
    ]
    if any(ind in title_lower for ind in first_in_series_indicators) or any(ind in desc_lower for ind in first_in_series_indicators):
        return "yes first in series"
        
    # 3. Later books check
    later_book_indicators = [
        "book 2", "book 3", "book 4", "book 5", "book 6", "book two", "book three",
        "book four", "book five", "vol 2", "vol 3", "volume 2", "volume 3", "sequel",
        "trilogy", "duology", "book #2", "book #3", "bk 2", "bk 3"
    ]
    if any(ind in title_lower for ind in later_book_indicators) or any(ind in desc_lower for ind in later_book_indicators):
        return "yes but can be read as standalone"
        
    return "no"


def classify_reading_list(profile, title, description, tags, word_count=0):
    """
    Classifies a story into a specific Reading List (RL) based on its Profile, Title, Description, and Tags.
    Supports Group 1 Profiles: Action / Adventure, Mystery / Thriller, Historical Fiction.
    """
    profile_lower = profile.lower() if profile else ""
    title_lower = title.lower() if title else ""
    desc_lower = description.lower() if description else ""
    tags_lower = [t.lower() for t in tags]
    
    def has_kw(*kws):
        return any(kw in title_lower or kw in desc_lower for kw in kws) or any(any(kw in tag for tag in tags_lower) for kw in kws)
        
    # 1. Action & Adventure
    if "action" in profile_lower or "adventure" in profile_lower:
        if has_kw("romance", "love", "heart", "marriage", "couple"):
            return "Action & Adventure Romances"
        if has_kw("crime", "mafia", "gangster", "gang", "mob", "heist", "thief", "steal"):
            return "Crime"
        if has_kw("hero", "heroes", "villain", "villains", "superhero", "powers"):
            return "Heroes & Villains"
        if has_kw("military", "war", "army", "soldier", "navy", "combat", "troop", "weapon"):
            return "Military & War"
        if has_kw("psychological", "psycho", "mind", "mental", "brain"):
            return "Psychological"
        if has_kw("spy", "spies", "assassin", "assassins", "agent", "cia", "undercover"):
            return "Spies & Assassins"
        if has_kw("sports", "sport", "football", "soccer", "basketball", "hockey", "baseball", "racing"):
            return "Sports"
        if has_kw("pirate", "pirates", "voyage", "voyages", "ship", "ocean", "sea", "sailing"):
            return "Pirates & Voyages"
        if has_kw("space", "galaxy", "alien", "aliens", "spaceship", "universe", "planet"):
            return "Space Adventures"
        if has_kw("cowboy", "cowboys", "western", "west", "sheriff", "horse"):
            return "Cowboys & Western"
        if has_kw("historical", "history", "ancient", "medieval", "century"):
            return "Historical Adventures"
        if has_kw("webtoon", "comic", "comics"):
            return "Webtoons & Comics"
        if has_kw("modern", "city", "new york", "london", "present"):
            return "Modern Adventures"
        return "Thriller"
        
    # 2. Mystery / Thriller
    elif "mystery" in profile_lower or "thriller" in profile_lower:
        if has_kw("murder", "kill", "homicide", "dead", "death", "victim", "case"):
            return "Murder"
        if has_kw("cozy"):
            return "Cozy"
        if has_kw("sleuth", "amateur", "investigate", "solve"):
            return "Amateur Sleuth"
        if has_kw("conspiracy", "secret", "secrets", "conspire", "government"):
            return "Conspiracy"
        if has_kw("noir", "gritty", "dark city"):
            return "Noir"
        if has_kw("caper", "heist", "robbery", "rob", "steal", "thief"):
            return "Caper"
        if has_kw("dark academia", "academy", "college", "school", "university", "professor"):
            return "Dark Academia"
        if has_kw("kidnap", "kidnapped", "kidnapping", "hostage", "abduction"):
            return "Kidnapping"
        if has_kw("detective", "police", "cop", "cops", "sheriff", "fbi", "officer", "police officer"):
            return "Detective and Police"
        return "A Mystery in General"
        
    # 3. Historical Fiction
    elif "historical" in profile_lower:
        if has_kw("kidnap", "kidnapping", "hostage"):
            return "Kidnapping"
        if has_kw("detective", "police", "cop", "cops", "sheriff", "fbi"):
            return "Detective and Police"
        if has_kw("16th century", "1500s", "1500"):
            return "16th Century"
        if has_kw("17th century", "1600s", "1600"):
            return "17th Century"
        if has_kw("18th century", "1700s", "1700"):
            return "18th Century"
        if has_kw("19th century", "1800s", "1800"):
            return "19th Century"
        if has_kw("20th century", "1900s", "1900"):
            return "20th Century"
        if has_kw("ancient", "rome", "greece", "egypt", "empire"):
            return "Ancient World"
        if has_kw("medieval", "middle ages", "knight", "knights", "castle", "sword"):
            return "Medieval"
        if has_kw("time slip", "time travel", "timeline"):
            return "Time Slip"
        if has_kw("regency", "duke", "duchess", "lord", "lady", "earl", "marquess"):
            return "Regency"
        if has_kw("victorian", "victoria"):
            return "Victorian"
        if has_kw("war", "battle", "soldier", "army"):
            return "War"
        if has_kw("royalty", "king", "queen", "prince", "princess", "crown", "throne"):
            return "Royalty"
        if has_kw("mythic", "epic", "myth", "myths", "legend", "legends", "god", "gods"):
            return "Mythic & Epic"
        return "Alternate History"
        
    # --- Group 2 ---
    
    # 4. Fright (Horror)
    elif "fright" in profile_lower or "horror" in profile_lower:
        if has_kw("psychological", "psycho", "mind", "mental", "insane", "madness"):
            return "Psychological"
        if has_kw("urban", "legend", "legends", "myth", "myths"):
            return "Urban Legends"
        if has_kw("zombie", "zombies", "undead", "apocalypse", "outbreak", "infected"):
            return "Zombies"
        if has_kw("gothic", "eldritch", "lovecraft", "ancient ones", "cthulhu"):
            return "Gothic & Eldritch"
        if has_kw("slasher", "slashers", "gore", "bloody", "butcher", "serial killer", "serialkiller"):
            return "Slashers & Gore"
        if has_kw("creature", "creatures", "cryptid", "cryptids", "monster", "monsters", "beast"):
            return "Creature & Cryptids"
        if has_kw("comedy", "funny", "humor", "hilarious", "spoof", "satire"):
            return "Comedy Horror"
        if has_kw("creepypasta", "creepy pasta", "slenderman", "jeff the killer"):
            return "Creepy Pasta"
        if has_kw("ghost", "ghosts", "haunted", "haunting", "hauntings", "phantom", "spirit", "spirits"):
            return "Ghosts & Hauntings"
        return "Psychological"
        
    # 5. Paranormal
    elif "paranormal" in profile_lower:
        if has_kw("occult", "afterlife", "underworld", "heaven", "hell", "reincarnation", "soul", "souls", "death"):
            return "Occult & Afterlife"
        if has_kw("academy", "academies", "school", "college", "university", "boardingschool"):
            return "Supernatural Academy"
        if has_kw("investigation", "investigate", "detective", "case", "solved", "cases"):
            return "Paranormal Investigation"
        if has_kw("witch", "witches", "witchcraft", "coven", "magic", "spell", "spells"):
            return "Witches"
        if has_kw("ghost", "ghosts", "phantom", "specter", "haunted", "spirit", "spirits"):
            return "Ghosts"
        if has_kw("fae", "faeries", "fairy", "fairies", "folklore", "folk", "mythology"):
            return "Fae & Folklore"
        if has_kw("angel", "angels", "demon", "demons", "devil", "lucifer", "fallen"):
            return "Angels & Demons"
        return "Supernatural Beings"
        
    # 6. Vampire
    elif "vampire" in profile_lower:
        if has_kw("academy", "academies", "boarding school", "vampire academy"):
            return "Academies"
        if has_kw("romance", "love", "mate", "mates", "lover", "lovers", "marriage", "wedding"):
            return "Traditional Romance"
        if has_kw("gothic", "dark", "classic", "dracula", "castle", "ancient"):
            return "Gothic Vampires"
        if has_kw("bloodline", "bloodlines", "royalty", "king", "queen", "prince", "princess", "clan", "clans"):
            return "Bloodlines & Royalty"
        if has_kw("hunter", "hunters", "slayer", "slayers", "van helsing", "kill", "hunt"):
            return "Hunters & Slayers"
        if has_kw("ya", "young adult", "teen", "high school", "highschool"):
            return "YA Vampires"
        return "Traditional Romance"
        
    # 7. Werewolf
    elif "werewolf" in profile_lower:
        # Check alpha romance / luna romance first
        if "luna" in title_lower or "luna" in desc_lower or "luna" in tags_lower:
            if has_kw("romance", "love", "mate", "mates"):
                return "Luna Romance"
        if "alpha" in title_lower or "alpha" in desc_lower or "alpha" in tags_lower:
            if has_kw("romance", "love", "mate", "mates"):
                return "Alpha Romance"
                
        if has_kw("rogue", "rogues", "packless", "banished", "exiled"):
            return "Rogues"
        if has_kw("omega", "omegaverse", "beta", "knot", "mating", "heat"):
            return "Omegaverse"
        if has_kw("fantasy", "scifi", "sci-fi", "space", "futuristic"):
            return "Fantasy-SF Werewolves"
        if has_kw("gothic", "dark", "horror", "blood", "moon", "curse"):
            return "Gothic Werewolves"
        if has_kw("shifter", "shifters", "shapeshifter", "pack", "packs"):
            return "World of Shifters"
        return "Alpha Romance"
        
    # --- Group 3 ---
    
    # 8. Fanfic (Fanfiction)
    elif "fanfic" in profile_lower or "fanfiction" in profile_lower:
        if has_kw("reader", "insert", "y/n", "yn", "reader insert", "x reader", "xreader"):
            return "Reader Inserts"
        if has_kw("fluff", "cute", "sweet", "wholesome"):
            return "Fanfic Fluff"
        if has_kw("kpop", "bts", "exo", "txt", "nct", "blackpink", "stray kids", "twice", "seventeen", "k-pop"):
            return "Kpop"
        if has_kw("anime", "manga", "naruto", "my hero academia", "mha", "bnha", "haikyu", "demonslayer", "attackontitan", "otaku"):
            return "Manga & Anime"
        if has_kw("wizarding", "hogwarts", "harry potter", "percy jackson", "percyjackson", "novel", "novels"):
            return "Books and Literature"
        if has_kw("webtoon", "webtoons", "comic", "comics", "manhwa", "webcomic"):
            return "Webtoons & Comics"
        if has_kw("famous", "celebrity", "actor", "actress", "youtuber", "influencer", "president"):
            return "Famous Figures"
        if has_kw("sport", "sports", "athlete", "athletes", "football", "soccer", "basketball", "player"):
            return "Sports and Athletes"
        if has_kw("game", "games", "gamer", "videogame", "minecraft", "genshin", "pokemon", "fnaf"):
            return "Video Games"
        if has_kw("movie", "movies", "film", "films", "marvel", "avengers", "star wars"):
            return "Movies"
        if has_kw("music", "singer", "singers", "band", "bands", "song", "songs", "one direction", "1d", "5sos"):
            return "Music"
        if has_kw("musical", "musicals", "theater", "broadway", "hamilton", "heathers"):
            return "Musicals and Theater"
        if has_kw("show", "shows", "series", "tv", "netflix", "stranger things", "supernatural"):
            return "Web & TV Shows"
        if has_kw("crossover", "crossovers", "x-over"):
            return "Crossovers"
        if has_kw("oc", "original character", "original characters"):
            return "Original Character"
        if has_kw("alternate reality", "ar", "shifting", "desired reality"):
            return "Alternate Reality"
        return "Alternate Universe"
        
    # 9. Fandoms
    elif "fandom" in profile_lower:
        if has_kw("bts", "bangtan", "jungkook", "jimin", "taehyung", "suga", "yoongi", "hoseok", "j-hope", "namjoon", "rm", "seokjin", "jin"):
            return "BTS"
        if has_kw("marvel", "avengers", "mcu", "spiderman", "spider-man", "ironman", "tony stark", "thor", "loki"):
            return "Marvel Universe"
        if has_kw("pokemon", "pikachu", "ash ketchum"):
            return "Pokemon"
        if has_kw("harry styles", "styles", "hs"):
            return "Harry Styles"
        if has_kw("one direction", "1d", "zayn", "liam", "louis", "niall"):
            return "One Direction"
        if has_kw("wizarding", "wizarding world", "hogwarts", "harry potter", "hermione", "ron weasley", "draco malfoy", "draco"):
            return "Wizarding World"
        if has_kw("5sos", "5 seconds of summer", "luke hemmings", "calum hood", "ashton irwin", "michael clifford"):
            return "5sos"
        if has_kw("my hero academia", "mha", "bnha", "deku", "bakugo", "todoroki"):
            return "My Hero Academia"
        if has_kw("exo", "chanyeol", "baekhyun", "sehun", "suho", "kai", "lay", "chen", "xiumin"):
            return "EXO"
        if has_kw("txt", "tomorrow x together", "yeonjun", "soobin", "beomgyu", "taehyun", "huening kai"):
            return "TXT"
        if has_kw("nct", "nct127", "nct dream", "wayv", "taeyong", "mark lee", "jaemin", "jeno"):
            return "NCT"
        if has_kw("minecraft", "mcyt", "dream smp", "dsmp", "steve"):
            return "Minecraft"
        if has_kw("haikyu", "haikyuu", "hinata", "kageyama", "karasuno", "oikawa"):
            return "Haikyu!!"
        if has_kw("blackpink", "bp", "jennie", "lisa", "jisoo", "rose"):
            return "Blackpink"
        if has_kw("stray kids", "skz", "bang chan", "felix", "hyunjin", "han", "leeknow", "changbin", "seungmin", "i.n"):
            return "Stray Kids"
        if has_kw("naruto", "sasuke", "kakashi", "sakura", "itachi", "konoha"):
            return "Naruto"
        return "Marvel Universe"
        
    # --- Group 4 ---
    
    # 10. Science Fiction
    elif "science" in profile_lower or "scifi" in profile_lower or "sci-fi" in profile_lower:
        if has_kw("litrpg", "system", "stats", "level up", "rpg", "gameworld"):
            return "LitRPG"
        if has_kw("dystopian", "apocalypse", "post-apocalyptic", "ruins", "wasteland", "survival", "dystocalypse"):
            return "Dystocalypse"
        if has_kw("cyberpunk", "neon", "megacorp", "implants", "cybernetic"):
            return "Cyberpunk"
        if has_kw("time travel", "time slip", "chronological", "time travel"):
            return "Time Travel"
        if has_kw("steampunk", "gears", "steam", "clockwork"):
            return "Steampunk"
        if has_kw("sci-fantasy", "science fantasy", "magic and tech"):
            return "Sci-Fantasy"
        if has_kw("exploration", "travel", "journey", "explore"):
            return "Space Exploration"
        if has_kw("alien", "aliens", "extraterrestrial", "ufo"):
            return "Aliens"
        if has_kw("robot", "robots", "ai", "artificial intelligence", "android", "cyborg"):
            return "Robots and AI"
        if has_kw("fleet", "galactic", "war", "battle", "conflict"):
            return "Galactic War"
        if has_kw("pandemic", "virus", "disease", "quarantine", "contagion"):
            return "Pandemic"
        if has_kw("zombie", "zombies", "undead", "infected"):
            return "Zombies"
        if has_kw("superhero", "superheroes", "mutant", "powers"):
            return "Superheroes"
        if has_kw("parallel", "dimension", "dimensions", "multiverse", "portal"):
            return "Parallel Universes"
        return "Space Exploration"
        
    # 11. Fantasy
    elif "fantasy" in profile_lower:
        if has_kw("dark fantasy", "grimdark", "dark", "gritty", "demon", "demons", "shadow", "curse"):
            return "Dark Fantasy"
        if has_kw("urban fantasy", "urban", "city", "modern", "hidden world", "secret society"):
            return "Urban Fantasy"
        if has_kw("isekai", "reborn", "reincarnated", "another world", "transmigrated"):
            return "Isekai"
        if has_kw("mythology", "folklore", "myth", "myths", "fairy tale", "fairytale", "legends"):
            return "Mythology & Folklore"
        if has_kw("academy", "academia", "school", "university", "magic school"):
            return "Academia"
        if has_kw("science fantasy", "tech", "spaceship", "magic"):
            return "Science Fantasy"
        if has_kw("magical realism", "realist", "surreal"):
            return "Magical Realism"
        if has_kw("romantasy", "romance", "love", "mate", "mates", "lovers"):
            return "Romantasy"
        if has_kw("ancient", "civilization", "rome", "egypt", "greece", "ruins"):
            return "Ancient Civilizations"
        if has_kw("god", "gods", "goddess", "goddesses", "deity", "divine"):
            return "Gods & Goddessess"
        if has_kw("kingdom", "kingdoms", "royalty", "king", "queen", "throne", "palace"):
            return "Magical Kingdoms"
        if has_kw("dragon", "dragons", "elf", "elves", "unicorn", "mythical", "creature", "creatures"):
            return "Mythical Creatures"
        if has_kw("pirate", "pirates", "voyage", "sea", "ship"):
            return "Pirates"
        if has_kw("wuxia", "xianxia", "cultivation", "sect", "qi", "martial arts"):
            return "Wuxia & Cultivation"
        return "Epic/High Fantasy"
        
    # --- Group 5 ---
    
    # 12. Romance
    elif "romance" in profile_lower:
        if has_kw("enemies to lovers", "enemies-to-lovers", "enemy", "enemies", "hate to love", "rival", "rivals"):
            return "Enemies to lovers"
        if has_kw("friends to lovers", "friends-to-lovers", "best friend", "bestfriend", "childhood friend", "childhood friends"):
            return "Friends to lovers"
        if has_kw("billionaire", "ceo", "billionaires", "ceos", "millionaire", "boss", "wealthy", "rich"):
            return "Billionaires and CEOs"
        if has_kw("fake relationship", "fake dating", "fake boyfriend", "fake girlfriend", "fake fiance"):
            return "Fake Relationships"
        if has_kw("arranged marriage", "arranged relationship", "arranged-marriage", "contract marriage", "force marriage", "forced marriage"):
            return "Arranged Relationships"
        if has_kw("hockey", "nhl", "ice hockey"):
            return "Hockey Romance"
        if has_kw("sport", "sports", "athlete", "athletes", "football", "soccer", "basketball", "player"):
            return "Sport Romance"
        if has_kw("workplace", "office", "coworker", "employee", "employer"):
            return "Workplace"
        if has_kw("second chance", "ex", "past love", "reunited", "regret"):
            return "Second Chance"
        if has_kw("romantic suspense", "suspense", "danger"):
            return "Romantic Suspense"
        if has_kw("slow burn", "slowburn", "slow-burn"):
            return "Slow Burn"
        if has_kw("romantasy", "fantasy romance", "magic", "fated mates"):
            return "Romantasy ♥"
        if has_kw("mafia", "gangster", "mob", "don", "cartel"):
            return "Mafia Romance"
        if has_kw("college", "university", "campus", "frat", "sorority"):
            return "College Romance"
        if has_kw("high school", "highschool", "teen", "school"):
            return "High School Romance"
        if has_kw("steamy", "hot", "sexy", "smut", "sensual", "spicy"):
            return "Steamy Romance"
        if has_kw("holiday", "christmas", "new year", "thanksgiving", "valentine"):
            return "Holiday Romance"
        if has_kw("love triangle", "triangle", "two guys", "two girls"):
            return "Love Triangle"
        if has_kw("romcom", "rom-com", "romantic comedy", "funny", "humor", "hilarious"):
            return "RomCom"
        if has_kw("cowboy", "cowboys", "ranch", "western"):
            return "Cowboy"
        if has_kw("destined", "fate", "destiny", "soulmate", "soulmates"):
            return "Destined Love"
        if has_kw("happy ending", "hea", "happily ever after"):
            return "Happy Ending"
        if has_kw("marriage", "divorce", "married", "husband", "wife"):
            return "Marriage & Divorce"
        if has_kw("opposites attract", "opposites-attract", "grumpy", "sunshine"):
            return "Opposites Attract"
        if has_kw("pregnant", "pregnancy", "baby", "secret baby"):
            return "Pregnancy"
        if has_kw("slice of life", "daily life", "everyday"):
            return "Slice of Life"
        if has_kw("small town", "town", "suburb", "community"):
            return "Small Town"
        if has_kw("tragedy", "sad", "death", "loss", "crying", "heartbreak"):
            return "Tragedy"
        return "Enemies to lovers"
        
    # 13. After Dark
    elif "afterdark" in profile_lower or "after dark" in profile_lower or "after-dark" in profile_lower:
        if has_kw("criminal", "crime", "mafia", "fugitive", "underground"):
            return "Criminal Romance"
        if has_kw("erotica", "erotic", "sexy", "mature", "adult"):
            return "Erotica"
        if has_kw("bdsm", "dominant", "submissive", "kink", "kinky", "leather", "collar"):
            return "BDSM"
        if has_kw("polyamory", "poly", "harem", "reverse harem", "rh", "why choose", "multiple lovers"):
            return "Why Choose & Polyamory"
        if has_kw("dark", "taboo", "gritty", "stalker", "obsessive", "kidnap"):
            return "Dark Romance"
        return "Dark Romance"
        
    # 14. LGBTQ+
    elif "lgbt" in profile_lower or "lgbtq" in profile_lower:
        if has_kw("coming out", "coming-out", "of age", "discovering", "identity"):
            return "Coming out & of Age"
        
        is_ya = has_kw("ya", "young adult", "teen", "high school", "school")
        
        if has_kw("boyxboy", "bxb", "bl", "gay", "manxman", "mxm"):
            if is_ya:
                return "BoyxBoy YA"
            else:
                return "ManxMan Adult"
                
        if has_kw("girlxgirl", "gxg", "wlw", "lesbian", "womanxwoman", "wxw"):
            if is_ya:
                return "GirlxGirl YA"
            else:
                return "WomanxWoman Adult"
                
        if has_kw("bisexual", "bi", "pansexual", "pan"):
            return "Bisexual & Pansexual"
        if has_kw("asexual", "aromantic", "ace", "aro"):
            return "Asexual/Aromantic"
        if has_kw("transgender", "trans", "ftm", "mtf"):
            return "Transgender"
        if has_kw("queer", "non-binary", "nonbinary", "nb", "genderqueer", "genderfluid"):
            return "Queer and Non-Binary"
        if has_kw("nonfiction", "non-fiction", "memoir", "biography"):
            return "Non-Fiction"
        if has_kw("diverse", "diversity", "poc", "multicultural"):
            return "DiverseLit"
        return "Queer and Non-Binary"
        
    # --- Group 6 ---
    
    # 15. Teen Fiction
    elif "teen" in profile_lower or "teenfiction" in profile_lower or "teenfic" in profile_lower:
        if has_kw("coming of age", "coming-of-age", "grow up", "growing up", "identity", "realize"):
            return "Coming-of-age"
        if has_kw("bad boy", "badboy", "rebel", "good girl"):
            return "Bad Boy Romance"
        if has_kw("sport", "sports", "athlete", "athletes", "football", "soccer", "basketball", "player"):
            return "Sports Romance"
        if has_kw("fake dating", "fake relationship", "fake boyfriend", "fake girlfriend"):
            return "Fake Dating"
        if has_kw("enemies to lovers", "enemies-to-lovers", "friends to lovers", "friends-to-lovers", "enemy", "enemies", "best friend"):
            return "Friend/Foe to Love"
        if has_kw("first love", "crush", "childhood crush"):
            return "First Love"
        return "Coming-of-age"
        
    # 16. Humor
    elif "humor" in profile_lower or "comedy" in profile_lower:
        if has_kw("satire", "parody", "spoof", "irony", "mock"):
            return "Satire & Parody"
        if has_kw("romance", "love", "romantic comedy", "romcom"):
            return "Romantic Comedy"
        if has_kw("dark comedy", "black comedy", "grim", "death", "gallows"):
            return "Dark Comedy"
        if has_kw("absurd", "absurdist", "surreal", "weird", "crazy"):
            return "Absurdist & Surreal"
        if has_kw("lighthearted", "light", "fun", "funny", "jokes", "joke", "silly"):
            return "Lighthearted humor"
        return "Lighthearted humor"
        
    # 17. ChickLit
    elif "chicklit" in profile_lower or "chick-lit" in profile_lower:
        if has_kw("romcom", "rom-com", "romantic comedy", "funny", "laugh"):
            return "Rom-Com"
        if has_kw("self-discovery", "discover", "finding myself", "journey", "growth"):
            return "Self-Discovery"
        if has_kw("drama", "secrets", "lies", "gossip", "betrayal"):
            return "High Drama"
        if has_kw("feminist", "feminism", "women empowerment", "independent woman"):
            return "Feminist Lit"
        if has_kw("experimental", "unique", "weird", "unconventional"):
            return "Experimental"
        if has_kw("career", "job", "work", "office", "promotion", "boss"):
            return "Career Women"
        if has_kw("wrong partner", "ex", "bad boyfriend", "cheating", "divorce"):
            return "Wrong partner"
        if has_kw("mother", "motherhood", "mom", "baby", "child"):
            return "Motherhood"
        if has_kw("family", "friends", "sisterhood", "brother", "parent"):
            return "Family and Friends"
        if has_kw("birthday", "turning 30", "turning 40", "birthday party"):
            return "Dreaded Birthday"
        if has_kw("glow up", "makeover", "transformation", "new me"):
            return "Glow Up"
        if has_kw("relatable", "ordinary girl", "normal girl", "heroine"):
            return "Relatable Heroine"
        return "Relatable Heroine"
        
    # --- Group 7 ---
    
    # 18. Poetry
    elif "poetry" in profile_lower or "poem" in profile_lower:
        if has_kw("lyrical", "song", "ballad", "melody"):
            return "Lyrical Poetry"
        if has_kw("narrative", "story", "tale", "chronicle"):
            return "Narrative Poetry"
        if has_kw("dramatic", "drama", "play", "dialogue"):
            return "Dramatic Poetry"
        if has_kw("special", "haiku", "sonnet", "limerick", "tanka"):
            return "Special Type Poetry"
        if has_kw("epic", "heroic", "myth", "odyssey", "saga"):
            return "Epic Poetry"
        if has_kw("pastoral", "nature", "countryside", "rural", "shepherd", "forest"):
            return "Pastoral Poetry"
        if has_kw("free verse", "freeverse", "unrhymed", "modern poetry"):
            return "Free Verse"
        if has_kw("prose", "poetic prose"):
            return "Prose"
        if has_kw("acrostic", "villanelle", "rhyme scheme"):
            return "Acrostic & Villanelle"
        if has_kw("stygian", "dark", "death", "gloom", "underworld", "shadows", "melancholy"):
            return "Stygian Themes"
        if has_kw("romantic woes", "heartbreak", "love", "sad love", "unrequited", "woe"):
            return "Romantic Woes"
        if has_kw("religious", "god", "faith", "prayer", "spiritual", "sacred"):
            return "Religious"
        if has_kw("collection", "anthology", "poems", "poetry book"):
            return "Collection"
        return "Free Verse"
        
    # 19. Short Story
    elif "short story" in profile_lower or "shortstory" in profile_lower:
        if has_kw("anthology", "anthologies", "collection", "collections", "short stories"):
            return "Anthologies"
        if word_count < 1000:
            return "Microfiction (< 1K)"
        if 1000 <= word_count < 3000:
            return "Quick Reads (1-3K)"
        if 3000 <= word_count < 5000:
            return "Short Shorts (3-5K)"
        if 5000 <= word_count < 10000:
            return "Medium Shorts (5-10K)"
        if 10000 <= word_count <= 20000:
            return "Novelettes (10-20K)"
        return "Medium Shorts (5-10K)"
        
    # --- Group 8 ---
    
    # 20. Non-Fiction
    elif "nonfiction" in profile_lower or "non-fiction" in profile_lower:
        if has_kw("memoir", "memoirs", "personal essay", "essay", "essays", "autobiography"):
            return "Memoir & Personal Essays"
        if has_kw("journalism", "investigative", "news", "report", "expose"):
            return "Journalism & Investigative"
        if has_kw("history of", "historical event", "history"):
            return "The History Of"
        if has_kw("food", "cooking", "recipe", "recipes", "kitchen", "chef", "bake", "baking"):
            return "Food & Cooking"
        if has_kw("spirituality", "philosophy", "spiritual", "philosophical", "god", "faith", "zen", "meditation"):
            return "Spirituality & Philosophy"
        if has_kw("cultural", "culture", "society", "perspectives", "heritage"):
            return "Cultural Perspectives"
        if has_kw("women", "woman", "feminist", "female", "girls", "sisterhood"):
            return "Women Voices"
        if has_kw("mind", "wellness", "health", "mental health", "self care", "self-care", "therapy", "psychology"):
            return "Mind & Wellness"
        if has_kw("travel", "traveling", "journal", "journals", "trip", "adventure", "globe"):
            return "Traveling Journals"
        if has_kw("how-to", "how to", "educational", "guide", "tutorial", "learn", "advice", "tips"):
            return "How-To & Educational"
        return "Memoir & Personal Essays"
        
    # 21. Social Themes
    elif "socialtheme" in profile_lower or "social theme" in profile_lower or "socialthemes" in profile_lower:
        if has_kw("abuse", "trauma", "toxic", "ptsd", "recovery", "survivor"):
            return "Abuse and Trauma"
        if has_kw("body positivity", "body positive", "plus size", "fat", "skinny", "appearance"):
            return "Body Positivity"
        if has_kw("coming of age", "coming-of-age", "grow up", "growing up"):
            return "Coming of Age"
        if has_kw("disability", "disabled", "wheelchair", "blind", "deaf", "mute", "amputee"):
            return "Disability"
        if has_kw("discrimination", "racism", "sexism", "homophobia", "prejudice"):
            return "Discrimination"
        if has_kw("family", "parents", "siblings", "brother", "sister", "home", "adoption", "foster"):
            return "Family Life"
        if has_kw("grief", "bereavement", "mourning", "loss", "death", "passed away"):
            return "Grief & Bereavement"
        if has_kw("illness", "disease", "cancer", "sick", "hospital", "chronic"):
            return "Illness"
        if has_kw("immigration", "refugee", "refugees", "immigrant", "border", "asylum"):
            return "Immigration/Refugees"
        if has_kw("neurodiversity", "adhd", "autism", "autistic", "dyslexia", "ocd"):
            return "Neurodiversity"
        if has_kw("religion", "spirituality", "church", "god", "faith", "temple", "mosque"):
            return "Religion/Spirituality"
        if has_kw("self-discovery", "identity", "find myself", "who am i"):
            return "Self-Discovery"
        return "Self-Discovery"
        
    # 22. Identity and Culture
    elif "identity" in profile_lower or "culture" in profile_lower:
        if has_kw("arab", "arabic", "middle east", "muslim"):
            return "Arab"
        if has_kw("black voices", "black", "african american", "afro", "blm"):
            return "Black Voices"
        if has_kw("caribbean", "jamaica", "haiti", "bahamas"):
            return "Caribbean"
        if has_kw("east african", "kenya", "ethiopia", "somalia"):
            return "East African"
        if has_kw("east asian", "china", "japan", "korea", "taiwan", "chinese", "japanese", "korean"):
            return "East Asian"
        if has_kw("european", "europe", "uk", "france", "germany", "italy", "spain"):
            return "European"
        if has_kw("hispanic", "spain", "latino"):
            return "Hispanic"
        if has_kw("indigenous", "native american", "aboriginal", "first nations"):
            return "Indigenous"
        if has_kw("latin american", "latino", "latina", "mexico", "brazil", "colombia", "argentina"):
            return "Latin American"
        if has_kw("north african", "egypt", "morocco", "algeria", "tunisia"):
            return "North African"
        if has_kw("pacific islander", "hawaii", "samoa", "fiji", "tonga"):
            return "Pacific Islander"
        if has_kw("south african", "south africa", "johannesburg", "cape town"):
            return "South African"
        if has_kw("south asian", "india", "pakistan", "bangladesh", "desi", "indian", "pakistani"):
            return "South Asian"
        if has_kw("southeast asian", "vietnam", "thailand", "philippines", "malaysia", "indonesia", "filipino"):
            return "Southeast Asian"
        if has_kw("west african", "west africa", "nigeria", "ghana", "senegal"):
            return "West African"
        if has_kw("interracial", "bwwm", "wmbw", "amwf", "wmaf", "mixed race"):
            return "Interracial"
        return "Multicultural"
        
    return ""



def cli_main():
    import argparse
    from epub_builder import EPUBBuilder

    parser = argparse.ArgumentParser(description="Wattpad Story Scraper and Downloader")
    parser.add_argument("url", help="The URL of the Wattpad story (landing page or a chapter page)")
    parser.add_argument("-f", "--format", choices=['epub', 'markdown', 'text', 'html', 'all'], default='epub',
                        help="Output format (default: epub)")
    parser.add_argument("-o", "--output-dir", default="./downloads", help="Output directory (default: ./downloads)")
    parser.add_argument("--delay-min", type=float, default=1.5, help="Minimum delay between requests (default: 1.5s)")
    parser.add_argument("--delay-max", type=float, default=2.5, help="Maximum delay between requests (default: 2.5s)")

    args = parser.parse_args()

    # Clean URL if it's a chapter link to point to story link (or keep it if it's already story link)
    url = args.url.strip()
    
    # If the URL is a chapter URL (like wattpad.com/123456-prologue), we can attempt to scrape it,
    # but the scraper handles story landing pages (wattpad.com/story/123456-title) best.
    # Let's tell the user to provide a story URL if we detect a chapter URL, or try to redirect them.
    if re.search(r'wattpad\.com/\d+[\w-]*$', url):
        print("Warning: You provided a chapter URL instead of a story landing URL.")
        print("We will attempt to scrape it, but if it fails, please copy and paste the main story URL.")

    # Create directories
    os.makedirs(args.output_dir, exist_ok=True)

    scraper = WattpadScraper(delay_min=args.delay_min, delay_max=args.delay_max)
    
    try:
        metadata = scraper.fetch_story_metadata(url)
    except Exception as e:
        print(f"Error fetching story metadata: {e}")
        sys.exit(1)

    print("\n--- Story Metadata ---")
    print(f"Title: {metadata['title']}")
    print(f"Author: {metadata['author']}")
    print(f"Chapters found: {len(metadata['chapters'])}")
    print("----------------------\n")

    if not metadata['chapters']:
        print("Error: No chapters found in this story!")
        sys.exit(1)

    chapters_content = []
    
    for idx, chapter in enumerate(metadata['chapters']):
        print(f"[{idx+1}/{len(metadata['chapters'])}] Fetching: {chapter['title']} (ID: {chapter['id']})...")
        try:
            html = scraper.fetch_chapter_html(chapter['id'])
            cleaned = scraper.clean_chapter_text(html)
            
            # Combine details
            chapter_data = {
                'id': chapter['id'],
                'title': chapter['title'],
                'url': chapter['url'],
                'text': cleaned['text'],
                'markdown': cleaned['markdown'],
                'xhtml': cleaned['xhtml']
            }
            chapters_content.append(chapter_data)
            
            # Wait to avoid rate limits
            if idx < len(metadata['chapters']) - 1:
                scraper.sleep_random()
        except Exception as e:
            print(f"Failed to fetch chapter '{chapter['title']}': {e}")
            # Ask to continue or exit
            choice = input("Would you like to skip this chapter and continue? (y/n): ")
            if choice.lower() != 'y':
                sys.exit(1)

    # Save outputs
    story_slug = re.sub(r'[\W_]+', '_', metadata['title'].lower()).strip('_')
    
    formats_to_save = [args.format] if args.format != 'all' else ['epub', 'markdown', 'text', 'html']

    if 'text' in formats_to_save:
        txt_path = os.path.join(args.output_dir, f"{story_slug}.txt")
        print(f"Saving Plain Text version to: {txt_path}")
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(f"{metadata['title']}\n")
            f.write(f"By {metadata['author']}\n\n")
            f.write(f"Description:\n{metadata['description']}\n\n")
            f.write("=" * 40 + "\n\n")
            for ch in chapters_content:
                f.write(f"--- {ch['title']} ---\n\n")
                f.write(ch['text'])
                f.write("\n\n")

    if 'markdown' in formats_to_save:
        md_path = os.path.join(args.output_dir, f"{story_slug}.md")
        print(f"Saving Markdown version to: {md_path}")
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(f"# {metadata['title']}\n\n")
            f.write(f"**Author:** {metadata['author']}\n\n")
            clean_desc_md = metadata['description'].replace('\n', '\n>')
            f.write(f"**Description:**\n>{clean_desc_md}\n\n")
            f.write("---\n\n")
            for ch in chapters_content:
                f.write(f"## {ch['title']}\n\n")
                f.write(ch['markdown'])
                f.write("\n\n")

    if 'html' in formats_to_save:
        html_path = os.path.join(args.output_dir, f"{story_slug}.html")
        print(f"Saving HTML version to: {html_path}")
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write("<!DOCTYPE html>\n<html>\n<head>\n")
            f.write(f"<meta charset=\"UTF-8\">\n<title>{metadata['title']}</title>\n")
            f.write("<style>body{font-family:sans-serif;max-width:700px;margin:40px auto;padding:0 20px;line-height:1.6;}h1{text-align:center;}h2{margin-top:40px;border-bottom:1px solid #ddd;padding-bottom:10px;}</style>\n")
            f.write("</head>\n<body>\n")
            f.write(f"<h1>{metadata['title']}</h1>\n")
            f.write(f"<p><strong>Author:</strong> {metadata['author']}</p>\n")
            f.write(f"<p><strong>Description:</strong> {metadata['description']}</p>\n")
            f.write("<hr/>\n")
            for ch in chapters_content:
                f.write(f"<h2>{ch['title']}</h2>\n")
                # Format into paragraphs
                paragraphs = ch['xhtml'].split('\n')
                for p in paragraphs:
                    f.write(f"{p}\n")
            f.write("</body>\n</html>")

    if 'epub' in formats_to_save:
        epub_path = os.path.join(args.output_dir, f"{story_slug}.epub")
        print(f"Compiling EPUB version to: {epub_path}")
        builder = EPUBBuilder(metadata, chapters_content)
        try:
            builder.build(epub_path)
            print("EPUB compilation successful!")
        except Exception as e:
            print(f"Error compiling EPUB: {e}")

    print("\nDownload process completed successfully!")


if __name__ == "__main__":
    cli_main()
