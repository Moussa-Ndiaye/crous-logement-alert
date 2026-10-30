
# Test indépendant : aucune connexion au site CROUS
# Aucun message Telegram, aucun fichier réel modifié

def filtrer(annonces):
    return {
        a["id"]: a
        for a in annonces
        if a["ville"].lower() in {
            "lille", "villeneuve-d'ascq", "roubaix",
            "tourcoing", "loosen", "lambersart"
        }
        and a["loyer"] <= 400
        and a["loyer"] > 0
        and a["lien"].startswith("https://")
    }


annonces_initiales = [
    {
        "id": "TEST-001",
        "ville": "Lille",
        "loyer": 350,
        "lien": "https://example.com/test-001"
    },
    {
        "id": "TEST-002",
        "ville": "Roubaix",
        "loyer": 450,
        "lien": "https://example.com/test-002"
    }
]

annonces_suivantes = [
    annonces_initiales[0],
    {
        "id": "TEST-003",
        "ville": "Villeneuve-d'Ascq",
        "loyer": 380,
        "lien": "https://example.com/test-003"
    }
]

deja_vues = set(filtrer(annonces_initiales))
nouvelles = {
    identifiant: annonce
    for identifiant, annonce
    in filtrer(annonces_suivantes).items()
    if identifiant not in deja_vues
}

assert len(deja_vues) == 1
assert len(nouvelles) == 1
assert "TEST-003" in nouvelles

print("TEST 1 : filtre 400 euros OK")
print("TEST 2 : nouvelle annonce detectee OK")
print("TEST 3 : annonce deja vue ignoree OK")
print("TEST TERMINE : 3 controles reussis")
