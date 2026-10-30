"""Surveillance prudente des offres publiques CROUS (aucune connexion)."""
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

SOURCE = os.environ.get('CROUS_SEARCH_URL', '')
STATE = Path('seen_logements.json')
MAX_PRICE = 400
# Filtrage géographique conservateur ; les offres sans ville identifiable sont ignorées.
CITIES = ('lille', 'villeneuve-d’ascq', "villeneuve-d'ascq", 'villeneuve d ascq',
          'roubaix', 'tourcoing', 'lambersart', 'loos', 'la madeleine', 'mons-en-baroeul',
          'mons-en-barœul', 'marcq-en-baroeul', 'marcq-en-barœul', 'ronchin',
          'hellemmes', 'faches-thumesnil', 'wasquehal', 'croix', 'haubourdin',
          'lezenne', 'lomme', 'saint-andre-lez-lille', 'saint-andré-lez-lille')
PRICE = re.compile(r'(?<!\d)(\d{2,4})(?:[,.](\d{1,2}))?\s*€', re.I)

def get_cards(page):
    # Pas d'API supposée : lecture des liens et de leurs conteneurs visibles.
    return page.evaluate('''() => {
      const base = location.origin;
      const out = [];
      for (const a of document.querySelectorAll('a[href]')) {
        const href = a.href;
        if (!href.startsWith(base) || !/\\/tools\\/\\d+\\/(?:accommodations?|logements?|residences?|housing|details?|search\\/[^?#/]+)/i.test(new URL(href).pathname)) continue;
        let el = a;
        for (let i=0; i<4 && el.parentElement; i++) {
          if ((el.innerText || '').includes('€')) break;
          el = el.parentElement;
        }
        const text = (el.innerText || '').replace(/\\s+/g,' ').trim();
        if (text.length >= 12 && text.length <= 1200) out.push({url:href, text});
      }
      return out;
    }''')

def extract(rows):
    listings = {}
    for row in rows:
        text = row['text']
        if not any(city in text.casefold() for city in CITIES):
            continue
        prices = [float(a + ('.' + b if b else '')) for a,b in PRICE.findall(text)]
        # Plusieurs montants => ambiguïté ; pas d'alerte.
        if len(prices) != 1 or not (0 < prices[0] <= MAX_PRICE):
            continue
        url = row['url'].split('#')[0]
        if not url.startswith('https://trouverunlogement.lescrous.fr/'):
            continue
        listings[url] = {'url':url, 'price':prices[0], 'description':text[:300]}
    return listings

def notify(item):
    token = os.environ['TELEGRAM_BOT_TOKEN']
    chat = os.environ['TELEGRAM_CHAT_ID']
    message = ('🏠 Nouvelle annonce CROUS potentielle (à vérifier)\n'
               f"💶 {item['price']:.2f} €/mois\n"
               f"📍 {item['description']}\n"
               f"🔗 {item['url']}")
    data = urllib.parse.urlencode({'chat_id':chat, 'text':message}).encode()
    req = urllib.request.Request(f'https://api.telegram.org/bot{token}/sendMessage', data=data)
    with urllib.request.urlopen(req, timeout=25) as response:
        result = json.load(response)
        if not result.get('ok'):
            raise RuntimeError('Telegram a refusé le message')

def main():
    parsed = urllib.parse.urlsplit(SOURCE)
    if parsed.scheme != 'https' or parsed.hostname != 'trouverunlogement.lescrous.fr':
        raise ValueError('CROUS_SEARCH_URL doit pointer vers le site officiel')
    q = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    q = [(k,v) for k,v in q if k != 'maxPrice'] + [('maxPrice',str(MAX_PRICE))]
    url = urllib.parse.urlunsplit(parsed._replace(query=urllib.parse.urlencode(q)))
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(locale='fr-FR')
        response = page.goto(url, wait_until='domcontentloaded', timeout=45000)
        if response is None or response.status >= 400:
            raise RuntimeError('Page CROUS inaccessible')
        page.wait_for_timeout(4500)
        if 'connexion' in page.title().lower() or 'login' in page.url.lower():
            raise RuntimeError('Authentification requise')
        rows = get_cards(page)
        print(f'Liens candidats: {len(rows)}')
        browser.close()
    if not rows:
        print('Aucun lien d’annonce reconnaissable : aucun état modifié, aucune notification.')
        return
    current = extract(rows)
    print(f'Annonces validées (<= 400 €): {len(current)}')
    if not current:
        print('Aucune annonce validée : état conservé, aucune notification.')
        return
    if not STATE.exists():
        STATE.write_text(json.dumps(sorted(current), ensure_ascii=False, indent=2) + '\n')
        print('État initial enregistré, aucune notification au premier passage.')
        return
    old = set(json.loads(STATE.read_text()))
    new = sorted(set(current) - old)
    for key in new:
        notify(current[key])
    # On conserve les annonces vues, pour éviter les doublons lors des réapparitions.
    STATE.write_text(json.dumps(sorted(old | set(current)), ensure_ascii=False, indent=2) + '\n')
    print(f'Nouvelles annonces notifiées : {len(new)}')

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'Échec de la vérification : {exc}', file=sys.stderr)
        sys.exit(1)
