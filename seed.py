import time
import requests
from decimal import Decimal
from datetime import date

from app.database import engine, SessionLocal
from app import models
from app.database import Base
from app.models.user import User
from app.models.pokemon import Pokemon
from app.models.card import Card, Grading
from app.models.listing import Listing

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

POKEMON_DATA = [
    {"pokedex_number": 6,   "name": "Charizard",  "primary_type": "Fire",     "secondary_type": "Flying",  "fun_fact": "Charizard flies around the sky in search of powerful opponents. Its fiery breath is capable of melting any material. If Charizard becomes truly angered, the flame at the tip of its tail burns in a light blue shade.", "description": "A flame Pokémon that is the final evolution of Charmander."},
    {"pokedex_number": 25,  "name": "Pikachu",    "primary_type": "Electric", "secondary_type": None,      "fun_fact": "Pikachu that can generate powerful electricity have cheek sacs that are extra soft and super stretchy. When it is angered, it immediately discharges the energy stored in the pouches in its cheeks.", "description": "The iconic electric mouse Pokémon and mascot of the franchise."},
    {"pokedex_number": 133, "name": "Eevee",      "primary_type": "Normal",   "secondary_type": None,      "fun_fact": "Eevee has an unstable genetic makeup that suddenly mutates due to the environment in which it lives. Radiation from various stones causes this Pokémon to evolve into one of eight different forms.", "description": "The evolution Pokémon with the most possible evolutions of any species."},
    {"pokedex_number": 143, "name": "Snorlax",    "primary_type": "Normal",   "secondary_type": None,      "fun_fact": "Snorlax's stomach is so strong it can digest any food—even if it's rotten or has thorns. It wakes up only to eat, consuming up to 900 pounds of food per day before going back to sleep.", "description": "The sleeping Pokémon known for blocking roads and being impossible to wake up."},
    {"pokedex_number": 150, "name": "Mewtwo",     "primary_type": "Psychic",  "secondary_type": None,      "fun_fact": "Mewtwo was created by a scientist after years of horrific gene-splicing and DNA-engineering experiments using Mew. It has the most savage heart among all Pokémon and strikes fear into its opponents.", "description": "The legendary genetic Pokémon created through science."},
    {"pokedex_number": 196, "name": "Espeon",     "primary_type": "Psychic",  "secondary_type": None,      "fun_fact": "Espeon is extremely loyal to any Trainer it considers worthy. To protect its Trainer from harm, it has developed precognitive powers using the fine hair that covers its body to sense air currents.", "description": "The sun Pokémon and one of Eevee's psychic evolutions."},
    {"pokedex_number": 197, "name": "Umbreon",    "primary_type": "Dark",     "secondary_type": None,      "fun_fact": "Umbreon evolved as a result of exposure to the moon's waves. It hides quietly in the darkness and waits for its foes to make a move. The rings on its body glow when it leaps to attack.", "description": "The moonlight Pokémon and one of Eevee's dark-type evolutions."},
    {"pokedex_number": 249, "name": "Lugia",      "primary_type": "Psychic",  "secondary_type": "Flying",  "fun_fact": "Lugia's wings pack devastating power—a light fluttering of its wings can blow apart regular houses. As a result, Lugia takes care not to fly and instead spends its time deep at the bottom of the sea.", "description": "The diving Pokémon and guardian of the seas."},
    {"pokedex_number": 384, "name": "Rayquaza",   "primary_type": "Dragon",   "secondary_type": "Flying",  "fun_fact": "Rayquaza lived for hundreds of millions of years in the ozone layer, never descending to the ground. It puts an end to battles between Kyogre and Groudon.", "description": "The sky high Pokémon that lives in the ozone layer."},
    {"pokedex_number": 151, "name": "Mew",        "primary_type": "Psychic",  "secondary_type": None,      "fun_fact": "Mew is said to possess the genetic composition of all Pokémon. It is capable of making itself invisible at will, so it entirely avoids notice even if it approaches people.", "description": "The mythical new species Pokémon said to contain all Pokémon DNA."},
    {"pokedex_number": 94,  "name": "Gengar",     "primary_type": "Ghost",    "secondary_type": "Poison",  "fun_fact": "Gengar is always lurking in the shadows. If you feel a sudden chill, it is certain that a Gengar appeared. It apparently wishes for a traveling companion.", "description": "The shadow Pokémon that hides in dark corners and cold spots."},
    {"pokedex_number": 130, "name": "Gyarados",   "primary_type": "Water",    "secondary_type": "Flying",  "fun_fact": "Gyarados is capable of causing massive destruction and flooding that can last for a whole month. It has an extremely aggressive nature.", "description": "The atrocious Pokémon that evolves from the weakest fish."},
    {"pokedex_number": 445, "name": "Garchomp",   "primary_type": "Dragon",   "secondary_type": "Ground",  "fun_fact": "Garchomp can fly at speeds comparable to a jet plane, folding its body to minimize air resistance. It preys on bird Pokémon and can catch them mid-flight.", "description": "The mach Pokémon that flies as fast as a jet."},
    {"pokedex_number": 448, "name": "Lucario",    "primary_type": "Fighting", "secondary_type": "Steel",   "fun_fact": "Lucario can read the minds of others by sensing their aura waves. It understands the feelings of Pokémon and people through the reading of these waves.", "description": "The aura Pokémon that can detect the feelings of others."},
    {"pokedex_number": 282, "name": "Gardevoir",  "primary_type": "Psychic",  "secondary_type": "Fairy",   "fun_fact": "Gardevoir has the ability to predict the future. If it senses impending danger to its Trainer, this Pokémon is said to unleash its psychokinetic energy at full power.", "description": "The embrace Pokémon that will sacrifice itself to protect its trainer."},
]

CARDS_DATA = [
    {"pokemon": "Charizard", "card_name": "Charizard VMAX",        "set_name": "Champions Path",   "set_code": "swsh35-74",  "card_number": "074/073", "rarity": "secret_rare", "card_variant": "rainbow",  "api_id": "swsh35-74"},
    {"pokemon": "Charizard", "card_name": "Charizard VMAX",        "set_name": "Darkness Ablaze",  "set_code": "swsh3-20",   "card_number": "020/189", "rarity": "ultra_rare",  "card_variant": "full_art", "api_id": "swsh3-20"},
    {"pokemon": "Charizard", "card_name": "Charizard",             "set_name": "Base Set",         "set_code": "base1-4",    "card_number": "4/102",   "rarity": "rare",        "card_variant": "holo",     "api_id": "base1-4"},
    {"pokemon": "Pikachu",   "card_name": "Pikachu",               "set_name": "Vivid Voltage",    "set_code": "swsh4-43",   "card_number": "043/185", "rarity": "rare",        "card_variant": "holo",     "api_id": "swsh4-43"},
    {"pokemon": "Pikachu",   "card_name": "Pikachu",               "set_name": "Base Set",         "set_code": "base1-58",   "card_number": "58/102",  "rarity": "common",      "card_variant": "normal",   "api_id": "base1-58"},
    {"pokemon": "Eevee",     "card_name": "Eevee",                 "set_name": "Fusion Strike",    "set_code": "swsh8-130",  "card_number": "130/264", "rarity": "uncommon",    "card_variant": "normal",   "api_id": "swsh8-130"},
    {"pokemon": "Eevee",     "card_name": "Eevee",                 "set_name": "Evolving Skies",   "set_code": "swsh7-128",  "card_number": "128/203", "rarity": "rare",        "card_variant": "holo",     "api_id": "swsh7-128"},
    {"pokemon": "Snorlax",   "card_name": "Snorlax",               "set_name": "Vivid Voltage",    "set_code": "swsh4-131",  "card_number": "131/185", "rarity": "rare",        "card_variant": "holo",     "api_id": "swsh4-131"},
    {"pokemon": "Snorlax",   "card_name": "Snorlax",               "set_name": "Base Set",         "set_code": "base1-11",   "card_number": "11/102",  "rarity": "rare",        "card_variant": "holo",     "api_id": "base1-11"},
    {"pokemon": "Mewtwo",    "card_name": "Mewtwo EX",             "set_name": "Next Destinies",   "set_code": "bw4-54",     "card_number": "54/99",   "rarity": "ultra_rare",  "card_variant": "full_art", "api_id": "bw4-54"},
    {"pokemon": "Mewtwo",    "card_name": "Mewtwo",                "set_name": "Base Set",         "set_code": "base1-10",   "card_number": "10/102",  "rarity": "rare",        "card_variant": "holo",     "api_id": "base1-10"},
    {"pokemon": "Espeon",    "card_name": "Espeon VMAX",           "set_name": "Evolving Skies",   "set_code": "swsh7-65",   "card_number": "065/203", "rarity": "ultra_rare",  "card_variant": "alt_art",  "api_id": "swsh7-65"},
    {"pokemon": "Umbreon",   "card_name": "Umbreon VMAX",          "set_name": "Evolving Skies",   "set_code": "swsh7-215",  "card_number": "215/203", "rarity": "secret_rare", "card_variant": "alt_art",  "api_id": "swsh7-215"},
    {"pokemon": "Umbreon",   "card_name": "Umbreon VMAX",          "set_name": "Evolving Skies",   "set_code": "swsh7-95",   "card_number": "095/203", "rarity": "ultra_rare",  "card_variant": "full_art", "api_id": "swsh7-95"},
    {"pokemon": "Lugia",     "card_name": "Lugia V",               "set_name": "Silver Tempest",   "set_code": "swsh12-186", "card_number": "186/195", "rarity": "secret_rare", "card_variant": "alt_art",  "api_id": "swsh12-186"},
    {"pokemon": "Lugia",     "card_name": "Lugia",                 "set_name": "Neo Genesis",      "set_code": "neo1-9",     "card_number": "9/111",   "rarity": "rare",        "card_variant": "holo",     "api_id": "neo1-9"},
    {"pokemon": "Rayquaza",  "card_name": "Rayquaza VMAX",         "set_name": "Evolving Skies",   "set_code": "swsh7-218",  "card_number": "218/203", "rarity": "secret_rare", "card_variant": "alt_art",  "api_id": "swsh7-218"},
    {"pokemon": "Rayquaza",  "card_name": "Rayquaza GX",           "set_name": "Celestial Storm",  "set_code": "sm7-109",    "card_number": "109/168", "rarity": "ultra_rare",  "card_variant": "full_art", "api_id": "sm7-109"},
    {"pokemon": "Mew",       "card_name": "Mew VMAX",              "set_name": "Fusion Strike",    "set_code": "swsh8-269",  "card_number": "269/264", "rarity": "secret_rare", "card_variant": "rainbow",  "api_id": "swsh8-269"},
    {"pokemon": "Mew",       "card_name": "Mew VMAX",              "set_name": "Fusion Strike",    "set_code": "swsh8-114",  "card_number": "114/264", "rarity": "ultra_rare",  "card_variant": "full_art", "api_id": "swsh8-114"},
    {"pokemon": "Gengar",    "card_name": "Gengar VMAX",           "set_name": "Fusion Strike",    "set_code": "swsh8-157",  "card_number": "157/264", "rarity": "ultra_rare",  "card_variant": "full_art", "api_id": "swsh8-157"},
    {"pokemon": "Gengar",    "card_name": "Gengar",                "set_name": "Base Set",         "set_code": "base1-5",    "card_number": "5/102",   "rarity": "rare",        "card_variant": "holo",     "api_id": "base1-5"},
    {"pokemon": "Gyarados",  "card_name": "Gyarados",              "set_name": "Base Set",         "set_code": "base1-6",    "card_number": "6/102",   "rarity": "rare",        "card_variant": "holo",     "api_id": "base1-6"},
    {"pokemon": "Garchomp",  "card_name": "Garchomp V",            "set_name": "Astral Radiance",  "set_code": "swsh10-118", "card_number": "118/189", "rarity": "ultra_rare",  "card_variant": "full_art", "api_id": "swsh10-118"},
    {"pokemon": "Lucario",   "card_name": "Lucario V",             "set_name": "Brilliant Stars",  "set_code": "swsh9-78",   "card_number": "078/172", "rarity": "ultra_rare",  "card_variant": "alt_art",  "api_id": "swsh9-78"},
    {"pokemon": "Gardevoir", "card_name": "Gardevoir ex",          "set_name": "Scarlet & Violet", "set_code": "sv1-86",     "card_number": "086/198", "rarity": "ultra_rare",  "card_variant": "full_art", "api_id": "sv1-86"},
]

LISTINGS_DATA = [
    {"seller": "pokéking99",    "card_idx": 0,  "price": 1_500_000,  "condition": "near_mint", "description": "Kondisi near mint, sudah disleeve sejak beli. No scratch."},
    {"seller": "bandungcards",  "card_idx": 3,  "price": 250_000,    "condition": "mint",      "description": "Freshly pulled dari booster pack. Mint banget."},
    {"seller": "jakartapokemon","card_idx": 12, "price": 3_200_000,  "condition": "mint",      "description": "Umbreon VMAX Alt Art EVS, grail card. Mint condition, toploader."},
    {"seller": "surabayadeck",  "card_idx": 9,  "price": 450_000,    "condition": "played",    "description": "Ada sedikit scratches di corner tapi masih oke buat played."},
    {"seller": "legendscards",  "card_idx": 16, "price": 2_800_000,  "condition": "mint",      "description": "Rayquaza VMAX Alt Art, one of the most beautiful cards ever printed."},
    {"seller": "bandungcards",  "card_idx": 5,  "price": 180_000,    "condition": "near_mint", "description": "Eevee Fusion Strike, sudah disleeve. Kondisi NM."},
    {"seller": "pokéking99",    "card_idx": 14, "price": 950_000,    "condition": "mint",      "description": "Lugia V Alt Art Silver Tempest. Sangat dicari, stok terbatas."},
    {"seller": "surabayadeck",  "card_idx": 19, "price": 600_000,    "condition": "near_mint", "description": "Mew VMAX Full Art. NM condition, stored in binder."},
    {"seller": "medancards",    "card_idx": 11, "price": 320_000,    "condition": "mint",      "description": "Espeon VMAX Alt Art, pulled sendiri. Mint, langsung sleeve."},
    {"seller": "legendscards",  "card_idx": 18, "price": 1_100_000,  "condition": "mint",      "description": "Mew VMAX Secret Rare Rainbow. Foil masih bagus banget."},
    {"seller": "pokéking99",    "card_idx": 1,  "price": 2_200_000,  "condition": "mint",      "description": "Charizard VMAX Full Art Darkness Ablaze. Grail piece."},
    {"seller": "jakartapokemon","card_idx": 24, "price": 1_400_000,  "condition": "near_mint", "description": "Lucario V Alt Art Brilliant Stars. NM, no whitening."},
    {"seller": "bandungcards",  "card_idx": 2,  "price": 8_500_000,  "condition": "near_mint", "description": "Charizard Base Set Shadowless Holo. Legendary card."},
    {"seller": "medancards",    "card_idx": 16, "price": 3_500_000,  "condition": "mint",      "description": "Rayquaza VMAX Secret Rare Alt Art, the crown jewel of EVS."},
    {"seller": "surabayadeck",  "card_idx": 22, "price": 750_000,    "condition": "played",    "description": "Gyarados Base Set Holo. Classic card, played condition tapi mulus."},
    {"seller": "legendscards",  "card_idx": 25, "price": 900_000,    "condition": "mint",      "description": "Gardevoir ex Scarlet & Violet Full Art. Brand new."},
    {"seller": "pokéking99",    "card_idx": 6,  "price": 280_000,    "condition": "mint",      "description": "Eevee EVS Holo. Beautiful art, mint condition."},
    {"seller": "jakartapokemon","card_idx": 13, "price": 2_800_000,  "condition": "near_mint", "description": "Umbreon VMAX Full Art EVS. Iconic card."},
    {"seller": "bandungcards",  "card_idx": 4,  "price": 1_200_000,  "condition": "near_mint", "description": "Pikachu Base Set — PSA graded!"},
    {"seller": "medancards",    "card_idx": 23, "price": 1_600_000,  "condition": "mint",      "description": "Garchomp V Full Art Astral Radiance. Mint, pulled sendiri."},
]

GRADING_DATA = [
    {"listing_idx": 12, "service": "PSA", "grade": "9.0",  "cert": "PSA-12345678", "graded_at": date(2023, 3, 15)},
    {"listing_idx": 0,  "service": "BGS", "grade": "9.5",  "cert": "BGS-87654321", "graded_at": date(2023, 8, 22)},
    {"listing_idx": 18, "service": "PSA", "grade": "10.0", "cert": "PSA-99887766", "graded_at": date(2022, 11, 5)},
]


def fetch_card_image(api_id: str):
    try:
        resp = requests.get(f"https://api.pokemontcg.io/v2/cards/{api_id}", timeout=8)
        if resp.status_code == 200:
            return resp.json()["data"]["images"]["large"]
        print(f"  warning: no image for {api_id} (status {resp.status_code})")
        return None
    except Exception as e:
        print(f"  warning: failed to fetch {api_id}: {e}")
        return None


def run():
    print("creating tables...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    try:
        if db.query(Pokemon).count() > 0:
            print("already seeded, skipping.")
            return

        print("seeding pokemon...")
        pokemon_map = {}
        for data in POKEMON_DATA:
            p = Pokemon(**data)
            db.add(p)
            db.flush()
            pokemon_map[data["name"]] = p

        print("seeding cards + fetching images...")
        cards = []
        image_cache = {}

        for i, data in enumerate(CARDS_DATA):
            api_id = data["api_id"]
            print(f"  [{i+1}/{len(CARDS_DATA)}] {data['card_name']} — {api_id}")

            if api_id not in image_cache:
                image_cache[api_id] = fetch_card_image(api_id)
                time.sleep(0.3)

            c = Card(
                pokemon_id=pokemon_map[data["pokemon"]].id,
                card_name=data["card_name"],
                set_name=data["set_name"],
                set_code=data["api_id"],
                card_number=data["card_number"],
                rarity=data["rarity"],
                card_variant=data["card_variant"],
            )
            db.add(c)
            db.flush()
            cards.append((c, api_id))

        print("seeding sellers...")
        sellers = {}
        for username in ["pokéking99", "bandungcards", "jakartapokemon", "surabayadeck", "legendscards", "medancards"]:
            u = User(
                username=username,
                email=f"{username.replace('é','e')}@example.com",
                hashed_password=pwd_context.hash("password123"),
                seller_rating=round(4.0 + (hash(username) % 10) / 10, 1),
                total_sales=(hash(username) % 50) + 5,
            )
            db.add(u)
            db.flush()
            sellers[username] = u

        print("seeding listings...")
        listings = []
        for data in LISTINGS_DATA:
            card, api_id = cards[data["card_idx"]]
            l = Listing(
                seller_id=sellers[data["seller"]].id,
                card_id=card.id,
                price=Decimal(str(data["price"])),
                condition=data["condition"],
                description=data["description"],
                status="active",
                image_urls=image_cache.get(api_id),
            )
            db.add(l)
            db.flush()
            listings.append(l)

        print("seeding graded listings...")
        for data in GRADING_DATA:
            listing = listings[data["listing_idx"]]
            g = Grading(
                grading_service=data["service"],
                grade=Decimal(data["grade"]),
                cert_number=data["cert"],
                graded_at=data["graded_at"],
            )
            db.add(g)
            db.flush()
            listing.grading_id = g.id
            listing.condition = None

        db.commit()
        print(f"\ndone! {len(POKEMON_DATA)} pokemon, {len(CARDS_DATA)} cards, {len(LISTINGS_DATA)} listings.")

    except Exception as e:
        db.rollback()
        print(f"error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()