import os
from bs4 import BeautifulSoup
from urllib.parse import unquote

class ConfluenceParser:
    def __init__(self, file_path):
        self.file_path = file_path
        self.soup = None
        self.title = None
        self.content_div = None
        self.images = [] # List of (img_tag, local_path)

    def add_inline_styles(self):
        """
        Inline styles for Confluence tables to ensure they render correctly in GLPI.
        GLPI often strips <style> tags, so inline styles on elements are safer.
        """
        if not self.soup:
            return

        # 1. Tables
        for table in self.soup.find_all('table', class_='confluenceTable'):
            # Merge existing style with new style
            existing = table.get('style', '')
            new_style = "border-collapse: collapse; width: 100%; margin: 10px 0; font-size: 14px;"
            table['style'] = f"{existing}; {new_style}".strip('; ')

        # 2. Table Headers (th)
        for th in self.soup.find_all('th', class_='confluenceTh'):
            existing = th.get('style', '')
            new_style = "border: 1px solid #ddd; padding: 8px; text-align: left; vertical-align: top; background-color: #f2f2f2; font-weight: bold; color: #333;"
            th['style'] = f"{existing}; {new_style}".strip('; ')

        # 3. Table Cells (td)
        for td in self.soup.find_all('td', class_='confluenceTd'):
            existing = td.get('style', '')
            new_style = "border: 1px solid #ddd; padding: 8px; text-align: left; vertical-align: top;"
            # specific highlight support
            if 'highlight' in td.get('class', []):
                new_style += " background-color: #fffae6;"
            
            td['style'] = f"{existing}; {new_style}".strip('; ')

    def parse(self):
        with open(self.file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        self.soup = BeautifulSoup(html_content, 'html.parser')
        
        # INJECT INLINE STYLES
        self.add_inline_styles()
        
        # 1. Extract Title (Raw)
        # Priority: h1#title-heading > title
        h1_title = self.soup.find('h1', id='title-heading')
        if h1_title:
            self.title = h1_title.get_text(strip=True)
        else:
            self.title = self.soup.title.string if self.soup.title else "Untitled"
        
        # 2. Extract Breadcrumbs
        # Usually <ol id="breadcrumbs"> or <div class="breadcrumbs">
        self.breadcrumbs = []
        bread_div = self.soup.find('div', class_='breadcrumbs')
        if not bread_div:
            bread_div = self.soup.find('ol', id='breadcrumbs')
            
        if bread_div:
            # Extract list items
            items = bread_div.find_all('li')
            for item in items:
                text = item.get_text(strip=True)
                # Remove numbers "1. ", "2. " if present
                # Regex remove leading digit
                import re
                clean_text = re.sub(r'^\d+\.\s*', '', text)
                if clean_text:
                    self.breadcrumbs.append(clean_text)

        # 3. Dynamic Title Cleaning
        # Remove prefix based on Space Name (First Breadcrumb)
        # e.g. Title: "Space Name : Page Title" -> "Page Title"
        clean_title = self.title.strip()
        
        if self.breadcrumbs:
            space_name = self.breadcrumbs[0]
            # Check if title strictly starts with space name
            # use lower case check to be safe or strict
            # Titles have " - " or " : " separator
            if clean_title.lower().startswith(space_name.lower()):
                 # Remove space name
                 clean_title = clean_title[len(space_name):].strip()
                 # Remove common separators at the start
                 clean_title = clean_title.lstrip(":- ").strip()
        
        self.title = clean_title

        # 4. Extract Content
        self.content_div = self.soup.find('div', id='main-content')
        if not self.content_div:
            # Fallback
            self.content_div = self.soup.find('body')

        if self.content_div:
            # Find images
            imgs = self.content_div.find_all('img')
            for img in imgs:
                src = img.get('src')
                if src:
                    # Resolve path
                    # Src is URL encoded, so unquote it
                    src = unquote(src)
                    
                    # Confluence export images are relative URL
                    # e.g. "attachments/123/456.png" or "../images/icon.gif"
                    
                    dir_name = os.path.dirname(self.file_path)
                    local_path = os.path.normpath(os.path.join(dir_name, src))
                    
                    self.images.append({
                        'tag': img,
                        'src': src,
                        'local_path': local_path
                    })

        # 5. Extract Metadata (Author/Date)
        # Usually in <div class="page-metadata">
        # Or look for pattern "Created by ... on ..."
        self.metadata_html = ""
        meta_div = self.soup.find('div', class_='page-metadata')
        if meta_div:
            # Convert to a nice paragraph
            # Fix: use separator=' ' to avoid "Created byName"
            text = meta_div.get_text(separator=' ', strip=True)
            self.metadata_html = f"<p style='color: #666; font-style: italic; font-size: 0.9em;'>{text}</p>"

    def resolve_user_mentions(self, login_cache):
        """
        Resolve Confluence @mentions to GLPI profile links.
        Finds <a class="confluence-userlink" data-username="login"> tags
        and replaces href with GLPI profile URL.

        Args:
            login_cache: dict of login_name (lowercase) -> user_id

        Returns:
            list: Unresolved usernames (not found in GLPI)
        """
        if not self.content_div:
            return []

        unresolved = []
        for link in self.content_div.find_all('a', class_='confluence-userlink'):
            username = link.get('data-username')
            if not username:
                continue

            user_id = login_cache.get(username.lower())
            if user_id is not None:
                link['href'] = f"/front/user.form.php?id={user_id}"
            else:
                if link.has_attr('href'):
                    del link['href']
                unresolved.append(username)

        return unresolved

    def resolve_metadata_users(self, fullname_cache_lookup):
        """
        Resolve author/editor in page metadata to GLPI profile links.
        Operates on self.soup (original HTML) to find spans,
        then rebuilds self.metadata_html with links.

        Args:
            fullname_cache_lookup: callable(display_name) -> user_id or None

        Returns:
            list: Unresolved display names (not found in GLPI)
        """
        if not self.soup:
            return []

        meta_div = self.soup.find('div', class_='page-metadata')
        if not meta_div:
            return []

        import html as html_module

        unresolved = []
        resolved = {}  # name -> user_id
        for span_class in ('author', 'editor'):
            span = meta_div.find('span', class_=span_class)
            if not span:
                continue

            name = span.get_text(strip=True)
            if not name:
                continue

            user_id = fullname_cache_lookup(name)
            if user_id is not None:
                resolved[name] = user_id
            else:
                unresolved.append(name)

        # Rebuild metadata_html: escape text first, then inject only our links
        text = html_module.escape(meta_div.get_text(separator=' ', strip=True))
        for name, user_id in resolved.items():
            escaped_name = html_module.escape(name)
            link_html = f'<a href="/front/user.form.php?id={int(user_id)}">{escaped_name}</a>'
            text = text.replace(escaped_name, link_html, 1)
        self.metadata_html = f"<p style='color: #666; font-style: italic; font-size: 0.9em;'>{text}</p>"

        return unresolved

    def get_content_html(self):
        """Return the modified inner HTML of the content div."""
        if self.content_div:
            return self.content_div.decode_contents()
        return ""

    def update_image_src(self, img_tag, new_src):
        """Update the src of a specific image tag."""
        img_tag['src'] = new_src
        # Remove data-image-src if present to avoid confusion
        if img_tag.has_attr('data-image-src'):
            del img_tag['data-image-src']
