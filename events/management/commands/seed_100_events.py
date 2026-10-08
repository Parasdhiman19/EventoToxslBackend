import random
from datetime import date, time, timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from accounts.models import User, OrganizerProfile
from events.models import Event, TicketTier, SavedEvent, EventLike

ORGANIZERS_DATA = [
    {
        'email': 'pulse.collective@evento.com',
        'name': 'Pulse Live Collective',
        'handle': 'pulse_live',
        'org_name': 'Pulse Live Collective',
        'bio': 'Pioneering modern underground electronic, indie pop, and sensory festival experiences.',
        'website': 'https://pulselive.io',
        'instagram': '@pulselive',
        'logo': 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=400&q=80',
    },
    {
        'email': 'nexus.studios@evento.com',
        'name': 'Nexus Stage Productions',
        'handle': 'nexus_stage',
        'org_name': 'Nexus Stage Productions Studio',
        'bio': 'Large-scale concert stages, arena audio-visual setups, and world-class live touring acts.',
        'website': 'https://nexusproductions.io',
        'instagram': '@nexusstage',
        'logo': 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&w=400&q=80',
    },
    {
        'email': 'techx.summits@evento.com',
        'name': 'TechX Summit Labs',
        'handle': 'techx_summits',
        'org_name': 'TechX Innovation Labs',
        'bio': 'Global developer conferences, AI hackathons, and venture capital innovation forums.',
        'website': 'https://techxsummits.org',
        'instagram': '@techx_labs',
        'logo': 'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?auto=format&fit=crop&w=400&q=80',
    },
    {
        'email': 'gourmet.guild@evento.com',
        'name': 'Gourmet Guild Curators',
        'handle': 'gourmet_guild',
        'org_name': 'The Gourmet Guild & Tasting Club',
        'bio': 'Michelin-guest chef tables, artisanal craft coffee cupping, and vineyard wine tours.',
        'website': 'https://gourmetguild.club',
        'instagram': '@gourmetguild',
        'logo': 'https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?auto=format&fit=crop&w=400&q=80',
    },
    {
        'email': 'prism.arts@evento.com',
        'name': 'Prism Visual Arts Wing',
        'handle': 'prism_arts',
        'org_name': 'Prism Contemporary Art Foundation',
        'bio': 'Contemporary sculpture showcases, darkroom analog photography, and generative digital installations.',
        'website': 'https://prismart.gallery',
        'instagram': '@prism_visualarts',
        'logo': 'https://images.unsplash.com/photo-1580489944761-15a19d654956?auto=format&fit=crop&w=400&q=80',
    },
    {
        'email': 'velvet.vault@evento.com',
        'name': 'Velvet Vault Club',
        'handle': 'velvet_vault',
        'org_name': 'Velvet Vault Nightlife Group',
        'bio': 'Exclusive rooftop sunset sessions, warehouse techno after-hours, and high-energy club nights.',
        'website': 'https://velvetvault.vip',
        'instagram': '@velvet_vault',
        'logo': 'https://images.unsplash.com/photo-1492562080023-ab3db95bfbce?auto=format&fit=crop&w=400&q=80',
    },
    {
        'email': 'craft.workshops@evento.com',
        'name': 'Maker Studio Hub',
        'handle': 'maker_studio',
        'org_name': 'Maker Studio & Craft Labs',
        'bio': 'Hands-on ceramics masterclasses, UI/UX bootcamps, woodwork ateliers, and barista training.',
        'website': 'https://makerstudio.space',
        'instagram': '@makerstudio_hub',
        'logo': 'https://images.unsplash.com/photo-1544005313-94ddf0286df2?auto=format&fit=crop&w=400&q=80',
    },
    {
        'email': 'horizon.festivals@evento.com',
        'name': 'Horizon Open Air',
        'handle': 'horizon_festivals',
        'org_name': 'Horizon Open Air Festivals',
        'bio': 'Multi-day outdoor music escapes, botanical lawn fairs, and bohemian indie camps.',
        'website': 'https://horizonfest.live',
        'instagram': '@horizonopenair',
        'logo': 'https://images.unsplash.com/photo-1519085360753-af0119f7cbe7?auto=format&fit=crop&w=400&q=80',
    },
]

ATTENDEES_DATA = [
    {'email': 'user@evento.com', 'name': 'Demo User (You)', 'city': 'Chandigarh'},
    {'email': 'aarav.sharma@demo.com', 'name': 'Aarav Sharma', 'city': 'Delhi'},
    {'email': 'ananya.iyer@demo.com', 'name': 'Ananya Iyer', 'city': 'Bengaluru'},
    {'email': 'rohan.mehta@demo.com', 'name': 'Rohan Mehta', 'city': 'Mumbai'},
    {'email': 'zoya.khan@demo.com', 'name': 'Zoya Khan', 'city': 'Chandigarh'},
    {'email': 'vikram.singh@demo.com', 'name': 'Vikramaditya Singh', 'city': 'Jaipur'},
    {'email': 'tanya.verma@demo.com', 'name': 'Tanya Verma', 'city': 'Mohali'},
    {'email': 'kabir.kapoor@demo.com', 'name': 'Kabir Kapoor', 'city': 'Delhi'},
    {'email': 'neha.reddy@demo.com', 'name': 'Neha Reddy', 'city': 'Hyderabad'},
    {'email': 'arjun.patel@demo.com', 'name': 'Arjun Patel', 'city': 'Pune'},
    {'email': 'priya.nair@demo.com', 'name': 'Priya Nair', 'city': 'Goa'},
    {'email': 'dev.malhotra@demo.com', 'name': 'Dev Malhotra', 'city': 'Chandigarh'},
    {'email': 'ishita.gupta@demo.com', 'name': 'Ishita Gupta', 'city': 'Delhi'},
    {'email': 'siddharth.rao@demo.com', 'name': 'Siddharth Rao', 'city': 'Bengaluru'},
    {'email': 'meera.joshi@demo.com', 'name': 'Meera Joshi', 'city': 'Mumbai'},
]

CITIES = [
    'Chandigarh', 'Mohali', 'Panchkula', 'Delhi NCR', 'Mumbai',
    'Bengaluru', 'Goa', 'Pune', 'Jaipur', 'Hyderabad'
]

# High quality, tested Unsplash photo collections
UNSPLASH_POOLS = {
    'Music & Concerts': [
        'https://images.unsplash.com/photo-1514525253161-7a46d19cd819?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1470225620780-dba8ba36b745?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1429962714451-bb934ecdc4ec?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1465847899084-d164df4dedc6?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1459749411175-04bf5292ceea?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1501386761578-eac5c94b800a?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1540039155733-5bb30b53aa14?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1493225457124-a3eb161ffa5f?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1482442120256-9c03866de390?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1508700115892-45ecd05ae2ad?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1516450360452-9312f5e86fc7?auto=format&fit=crop&w=1200&q=80',
    ],
    'Tech & Conferences': [
        'https://images.unsplash.com/photo-1511578314322-379afb476865?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1505373877841-8d25f7d46678?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1531482615713-2afd69097998?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1515187029135-18ee286d815b?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1542744173-8e7e53415bb0?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1488590528505-98d2b5aba04b?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1551836022-d5d88e9218df?auto=format&fit=crop&w=1200&q=80',
    ],
    'Food & Tasting': [
        'https://images.unsplash.com/photo-1442512595331-e89e73853f31?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1555396273-367ea4eb4db5?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1555939594-58d7cb561ad1?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1551218808-94e220e084d2?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1510812431401-41d2bd2722f3?auto=format&fit=crop&w=1200&q=80',
    ],
    'Nightlife': [
        'https://images.unsplash.com/photo-1566737236500-c8ac43014a67?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1571266028243-3716f02d2d2e?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1517457373958-b7bdd4587205?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1574391884720-bbc3740c59d1?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1492684223066-81342ee5ff30?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1516450360452-9312f5e86fc7?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1545128485-c400e7702796?auto=format&fit=crop&w=1200&q=80',
    ],
    'Art & Exhibitions': [
        'https://images.unsplash.com/photo-1536924940846-227afb31e2a5?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1579783902614-a3fb3927b675?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1561214115-f2f134cc4912?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1460661419201-fd4cecdf8a8b?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1577083552431-6e5fd01aa342?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1547891654-e66ed7ebb968?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1518998053901-5348d3961a04?auto=format&fit=crop&w=1200&q=80',
    ],
    'Workshops': [
        'https://images.unsplash.com/photo-1522202176988-66273c2fd55f?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1531403009284-440f080d1e12?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1581091226825-a6a2a5aee158?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1452860606245-08befc0ff44b?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1517048676732-d65bc937f952?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1513542789411-b6a5d4f31634?auto=format&fit=crop&w=1200&q=80',
    ],
    'Club Night': [
        'https://images.unsplash.com/photo-1574391884720-bbc3740c59d1?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1516450360452-9312f5e86fc7?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1566737236500-c8ac43014a67?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1571266028243-3716f02d2d2e?auto=format&fit=crop&w=1200&q=80',
    ],
    'Conference': [
        'https://images.unsplash.com/photo-1511578314322-379afb476865?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1505373877841-8d25f7d46678?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1542744173-8e7e53415bb0?auto=format&fit=crop&w=1200&q=80',
    ]
}

EVENT_TEMPLATES = [
    # Music (22 templates)
    ("Acoustic Sunsets: Mountain Folk & Strings", "Music & Concerts", "An intimate open-air twilight session featuring acoustic fingerstyle guitar, cellos, and indie folk ballads under Himalayan pines.", "Pine Grove Amphitheatre", 25, 60),
    ("Electric Monsoon 2026: Open Air Bass", "Music & Concerts", "Two stages of immersive dub, liquid drum & bass, and UK garage powered by heavyweight custom sound systems.", "Northland Arena Grounds", 35, 95),
    ("Neon Symphony: Orchestral Synthesizers", "Music & Concerts", "A 30-piece live philharmonic orchestra meets analog modular synthesisers performing cyberpunk film scores.", "Grand Opera Hall", 45, 120),
    ("Desert Mirage: Psytrance & Ambient Camp", "Music & Concerts", "A multi-sensory desert gathering with psychedelic visuals, fire dancers, and international progressive trance acts.", "Dune Oasis Camp", 50, 140),
    ("Soul & Brass Revue: Live Jazz Sessions", "Music & Concerts", "Classic Chicago blues, contemporary soul, and high-energy 8-piece brass ensemble in a speakeasy ballroom.", "The Velvet Lounge", 30, 80),
    ("Midnight Lo-Fi Beats & Chillhop Live", "Music & Concerts", "Live beatmakers, jazz keys, and chill instrumental hip-hop in a cozy beanbag lounge setup with visual projections.", "Subculture Basement", 15, 40),
    ("Echoes of Punjab: Modern Sufi & Qawwali", "Music & Concerts", "Spellbinding traditional sufi poetry blended with ambient soundscapes and acoustic harmoniums in an open courtyard.", "Heritage Fort Courtyard", 30, 85),
    ("Retro Rewind: 80s Synthwave Night", "Music & Concerts", "Outrun visual aesthetics, arcade machines, laser arrays, and live synthwave artists spinning 1980s neon nostalgia.", "Cyber Arcade Club", 20, 50),
    ("Himalayan Soundscapes: Tribal & World Music", "Music & Concerts", "Didgeridoos, handpans, overtone singing, and meditative world rhythms echoing against natural stone hills.", "Echo Valley Retreat", 35, 90),
    ("Indie Wave Festival: Day & Night Showcase", "Music & Concerts", "Twelve breakout indie-rock and dream-pop acts performing back-to-back across two stages with artisan food trucks.", "Urban Forest Meadows", 40, 110),
    ("Sunset Reggae & Dub Soundclash", "Music & Concerts", "Roots reggae, dubplates, and sunshine positive vibrations by the beach with fresh coconuts and jerk barbecue.", "Palm Grove Beachfront", 25, 60),
    ("Raw Metal Mayhem: Heavy Riffs Fest", "Music & Concerts", "Hardcore, progressive metal, and thundering double-kick drums featuring premier underground regional bands.", "The Ironworks Warehouse", 20, 55),
    ("Tokyo City Pop & Funk Experience", "Music & Concerts", "Shibuya-kei, Japanese funk grooves, and 70s disco revival on high-fidelity analog vinyl audio setups.", "Ginza Vinyl Bar", 25, 65),
    ("Bassline Carnival: UK Funky & Grime", "Music & Concerts", "High-octane MCs, rumbling sub-frequencies, and raw street energy celebrating modern British bass cultures.", "Underpass Studio B", 20, 50),
    ("Piano Under the Stars: Classical Solo", "Music & Concerts", "A Steinway concert grand piano placed in an open lawn garden playing Chopin, Debussy, and Ludovico Einaudi.", "Botanical Glasshouse Gardens", 35, 90),
    ("Flamenco & Guitar Fusions", "Music & Concerts", "Passionate Spanish flamenco footwork, percussion cajons, and virtuosic Spanish guitar duet arrangements.", "Casa Bellas Artes", 30, 75),
    ("Deep House Sundowner on the Pier", "Music & Concerts", "Melodic house, organic grooves, and chilled champagne cocktails as the orange sun slips into the horizon.", "Marina Bay Pier Deck", 35, 100),
    ("Post-Rock Immersion: Crescendo & Distortion", "Music & Concerts", "Epic 15-minute ambient swells, delay pedal walls of sound, and cinematic black-and-white visuals.", "The Blackbox Space", 25, 70),
    ("Global Beats: Afrohouse & Latin Percussion", "Music & Concerts", "Hypnotic live batá drums, tribal afro-tech synthesizers, and non-stop dancing under open tropical skies.", "Terraza Rooftop", 25, 65),
    ("Hip-Hop Cypher & Freestyle Battle Arena", "Music & Concerts", "Live beatboxers, 16-bar bracket tournaments, and showcase performances by top tier lyrical storytellers.", "Graffiti Yard 4", 15, 35),
    ("Balkan Gypsy Brass & Balkan Beats", "Music & Concerts", "Blistering trumpet solos, ecstatic accordion runs, and joyous celebratory Eastern European folk dance rhythms.", "The Bohemian Tent", 20, 50),
    ("Dream Pop Sessions: Reverb & Starlight", "Music & Concerts", "Ethereal shoegaze, shimmering chorus pedals, and floating female vocals in a fairy-light illuminated glass atrium.", "The Glass Atrium", 25, 60),

    # Tech & Conferences (16 templates)
    ("AI Frontier Summit 2026: Large Models & Agents", "Tech & Conferences", "World-renowned machine learning researchers and founders debating the next horizon of autonomous agent systems.", "Silicon Convention Hall A", 75, 250),
    ("Web3 & Decentralized Infrastructure Forum", "Tech & Conferences", "Zero-knowledge cryptography, decentralized data layers, and open sovereign identity systems.", "Nexus Innovation Hub", 50, 180),
    ("Full-Stack Cloud Architecture Masterclass", "Tech & Conferences", "Real-world microservices case studies, Kubernetes at massive scale, and zero-downtime database migrations.", "TechPark Auditorium", 40, 120),
    ("DevOps & Platform Engineering Days", "Tech & Conferences", "Observability pipelines, internal developer platforms, and infrastructure-as-code production strategies.", "Metro Center 3", 45, 130),
    ("Product Design & UX Vision 2026", "Tech & Conferences", "Design systems at scale, spatial interfaces, micro-interactions, and AI-accelerated Figma workflows.", "Design Center Auditorium", 35, 110),
    ("Cybersecurity Threat Matrix & Red Team Live", "Tech & Conferences", "Live penetration testing demos, zero-day threat intelligence, and enterprise hardening blueprints.", "CyberSec Lab Theatre", 60, 200),
    ("NextGen Frontend Conf: Vite, React & Beyond", "Tech & Conferences", "The bleeding-edge of browser runtimes, server components, compiler optimizations, and web performance.", "Developers Den Hub", 35, 95),
    ("Autonomous Systems & Robotics Expo", "Tech & Conferences", "Drone navigation, industrial automation arms, and computer vision neural nets in action on test arenas.", "Pavilion of Robotics", 50, 160),
    ("Quantum Computing: From Theory to Qubits", "Tech & Conferences", "Physicists and quantum software engineers demystifying superconducting circuits and quantum algorithms.", "National Science Center", 55, 175),
    ("Game Engine Architecture & Real-Time VFX", "Tech & Conferences", "Unreal Engine 5 nanite pipelines, procedural world generation, and mobile GPU compute optimization.", "Digital Arts Studio", 40, 120),
    ("BioTech Horizons: Synthetic Biology & Data", "Tech & Conferences", "CRISPR delivery vectors, algorithmic protein folding, and the future of personalized medicine computational tools.", "BioInnovate Center", 65, 210),
    ("CleanTech & Renewable Energy Summit", "Tech & Conferences", "Next-gen battery chemistries, microgrid balancing software, and carbon accounting enterprise tools.", "Green Valley Convention", 45, 140),
    ("Data Engineering & Streaming Pipelines Conf", "Tech & Conferences", "Kafka, Flink, Iceberg, and real-time analytical warehouses processing billions of events per second.", "DataSphere Center", 50, 150),
    ("Mobile Engineering World: Swift, Kotlin & Flutter", "Tech & Conferences", "Offline-first architecture, mobile CI/CD pipelines, and app startup latency engineering at scale.", "CodeCraft Theatre", 35, 100),
    ("AR & Spatial Computing Developer Days", "Tech & Conferences", "Hands-on visionOS and WebXR labs, volumetric capture pipelines, and gestural interface design principles.", "Virtual Horizons Lab", 55, 165),
    ("Fintech Architecture: Ledger & Payment Rails", "Tech & Conferences", "High-frequency settlement engines, regulatory compliance automation, and distributed double-entry ledgers.", "Financial District Ballroom", 60, 190),

    # Food & Tasting (16 templates)
    ("Artisan Sourdough & Fermentation Festival", "Food & Tasting", "Ancient heirloom grain bakeries, live wild-yeast starter tastings, and cultured butter pairing flights.", "The Old Granary Yard", 20, 50),
    ("Smoked Texas BBQ Pitmaster Invitational", "Food & Tasting", "14-hour smoked oak briskets, glazed pork ribs, scratch-made cornbread, and spicy heritage coleslaws.", "Smokehouse Lawn Grounds", 35, 80),
    ("Single Origin Coffee Cupping & Roaster Guild", "Food & Tasting", "Evaluate geishas and washed Ethiopians with international Q-graders using SCA sensory wheel standards.", "Roaster Lab Sector 9", 25, 60),
    ("Craft Beer & Microbrewery Autumn Fest", "Food & Tasting", "Over 40 limited-run IPAs, bourbon-barrel imperial stouts, and fruited kettle sours poured fresh from the tap.", "Riverside Breweries Lawn", 30, 75),
    ("Napoli Pizza Master Showcase: Wood-Fired", "Food & Tasting", "World-champion pizzaiolos baking San Marzano DOP pies at 900 degrees with fior di latte and fresh basil.", "Piazza Bella Vista", 25, 55),
    ("Artisanal Cheese & Wine Pairing Salon", "Food & Tasting", "Cave-aged gruyères, French triple-crèmes, and sharp raw-milk cheddars paired with biodynamic natural wines.", "Cellar 14 Barrel Room", 45, 110),
    ("Street Food Fiesta: Pan-Asian Night Market", "Food & Tasting", "Sizzling bao buns, Taiwanese fried chicken, pad thai woks, and matcha shaved ice desserts under lantern glow.", "Night Market Promenade", 15, 45),
    ("Chocolate Alchemy: Bean-to-Bar Workshop", "Food & Tasting", "Single-estate cocoa bean roasting, stone-grinder conching, and tempered dark chocolate bar craft.", "Cacao Studio Works", 30, 70),
    ("Tacos, Mezcal & Agave Heritage Night", "Food & Tasting", "Handmade nixtamal corn tortillas, slow-braised birria, and smoky ancestral mezcals from Oaxaca.", "Hacienda Patio", 30, 75),
    ("Farm-to-Table Autumn Harvest Long Table", "Food & Tasting", "An 80-person communal banquet in a working orchard featuring heirloom squash, truffles, and roast lamb.", "Sunburst Organic Farm", 60, 150),
    ("Matcha Ceremony & Japanese Wagashi Tasting", "Food & Tasting", "Traditional Uji ceremonial grade whisked matcha served alongside handmade seasonal bean paste wagashi confections.", "Zen Pavilion & Tea Room", 35, 85),
    ("Mediterranean Olive Oil & Meze Experience", "Food & Tasting", "First cold-pressed extra virgin oils from Greece and Spain paired with freshly baked pita, labneh, and olives.", "The Olive Court", 25, 60),
    ("Ramen & Gyoza Masterclass Dinner", "Food & Tasting", "18-hour rich tonkotsu broth, hand-pulled alkali noodles, chashu pork belly, and crispy lacy gyoza dumplings.", "Noodle House Studio", 35, 80),
    ("The Great Gelato & Pastry Carnival", "Food & Tasting", "Pistachio di Bronte, salted honeycomb, and dark chocolate sorbettos alongside fresh cannoli and croissants.", "Dolce Garden Plaza", 20, 45),
    ("Spices of the Silk Road: Royal Mughlai Feast", "Food & Tasting", "Dum pukht biryanis, saffron-infused lamb shanks, and charcoal kebabs prepared by traditional master ustads.", "Darbar Royal Courtyard", 40, 100),
    ("Natural Wine & Pet-Nat Lawn Picnic", "Food & Tasting", "Unfiltered orange wines, effervescent pét-nats, and fresh sourdough tartines on checkered lawn blankets.", "Vineyard Green Lawns", 35, 85),

    # Nightlife & Club Night (16 templates)
    ("Sub-Bass Bunker: Underground Techno 140BPM", "Nightlife", "A converted subterranean concrete boiler room featuring modular industrial techno and stroke lighting.", "Sub-Level Boiler Room", 25, 60),
    ("Sunset Rooftop Sessions: Melodic Progressive", "Nightlife", "Golden hour vibes overlooking the city skyline with deep melodic house grooves and craft botanic cocktails.", "Altitude 360 Lounge", 30, 75),
    ("Neon Disco Odyssey: Nu-Disco & Funk", "Nightlife", "Glitter balls, roller skates, vocoders, and irresistible disco basslines keeping the floor moving until 4 AM.", "Studio 54 Revival Hall", 20, 50),
    ("Boiler Room Style: 360 Degree DJ Booth", "Club Night", "Crowd surrounding the selector in a raw warehouse circle with close-up multi-camera livestream setups.", "Sector 17 Warehouse", 30, 80),
    ("Latin Heat: Salsa, Bachata & Reggaeton Club", "Nightlife", "Live brass percussion, sensual tropical rhythms, and non-stop dancing across two temperature-controlled floors.", "Havana Club & Cantina", 20, 50),
    ("Dark Wave & Post-Punk Midnight Gathering", "Nightlife", "Goth synths, heavy basslines, analog drum machines, and haze-filled atmospheric lighting for dark souls.", "The Crypt Underground", 20, 45),
    ("Electric Masquerade: Midnight Carnival", "Nightlife", "Dramatic masks, velvet drapes, aerial ribbon performers, and high-energy progressive house euphoria.", "Grand Ballroom Palais", 45, 120),
    ("Hardstyle Overdrive: 150BPM Festival Night", "Club Night", "Earth-shaking distorted kicks, reverse basslines, and laser arrays lighting up an indoor arena.", "Thunderdome Arena B", 25, 65),
    ("Afrobeats & Amapiano Rooftop Takeover", "Nightlife", "Log drum basslines, piano chords, and viral dance routines on a warm open rooftop under the stars.", "Skyline Terrace Sector 26", 25, 60),
    ("DnB Jungle Pressure: Dubplate Special", "Nightlife", "Old-school jungle breaks, ragga vocals, and relentless 174BPM rolling basslines through horn speakers.", "Subway Tunnel Hall", 20, 55),
    ("Ibiza White Party: Deep Organic House", "Nightlife", "All-white dress code, eucalyptus scents, chilled champagne, and balearic guitar grooves till sunrise.", "Playa Vista Club", 40, 110),
    ("Vinyl Only: Deep Minimal & Microhouse", "Club Night", "Two turntables, pristine rotary mixers, and warm analog grooves spun by seasoned vinyl crate diggers.", "The Listening Cellar", 25, 60),
    ("Retro Gaming & Chiptune Rave", "Nightlife", "Game Boy synthesizers, 16-bit arcade projectors, neon drinks, and high-energy chiptune dance music.", "Arcadia Cyber Bar", 15, 40),
    ("Trance Sanctuary: Uplifting 138BPM", "Club Night", "Euphoric piano breakdowns, soaring pads, and emotional vocal anthems transporting 2,000 clubbers.", "Sanctuary Arena Hall", 30, 85),
    ("Secret Speakeasy: Jazz, Gin & Electro-Swing", "Nightlife", "Password-entry bookcase door, vintage flapper glamour, brass saxophones, and swinging modern beats.", "The Bookcase Vault", 35, 90),
    ("Glow in the Dark: UV Paint Laser Party", "Club Night", "Fluorescent body artists, blacklight strobe cannons, and euphoric EDM anthems on a pulsating dance floor.", "Prism Club Zone", 20, 50),

    # Art & Exhibitions (16 templates)
    ("Generative Light & Shadows: Digital Art", "Art & Exhibitions", "Interactive projections mapping visitor body movements into swirling mathematical particle simulations.", "Prism Media Pavilion", 20, 55),
    ("Monochrome Streets: 35mm Analog Photography", "Art & Exhibitions", "Handmade silver gelatin darkroom prints chronicling urban railway stations and mid-century architecture.", "Sector 8 Art Wing", 15, 40),
    ("Sculpting the Void: Modern Steel & Stone", "Art & Exhibitions", "Monumental welded corten steel structures and chiseled raw marble exploring spatial negative space.", "Open Sculpture Lawn", 25, 65),
    ("The Botanical Herbarium: Flora Illustration", "Art & Exhibitions", "Historical hand-painted botanical pressings, scientific plant prints, and living moss installations.", "Heritage Glass Atrium", 15, 35),
    ("Ceramic Forms: Japanese Raku & Wabi-Sabi", "Art & Exhibitions", "Wood-fired stoneware tea bowls, cracked glaze vases, and natural unglazed earthy terracotta sculptures.", "Clay Studio Gallery", 20, 45),
    ("Typography & The Letterpress Revival", "Art & Exhibitions", "Antique Heidelberg press posters, wooden type specimen prints, and contemporary graphic design manifestos.", "The Printing Atelier", 15, 35),
    ("Vivid Horizons: Abstract Oil Canvas Solo", "Art & Exhibitions", "Thick palette-knife impasto landscapes evoking stormy mountain ridges and desert canyon sunsets.", "Modernist Gallery 4", 25, 60),
    ("Kinetic Sculptures: Wind, Gravity & Wire", "Art & Exhibitions", "Delicate mobile wire sculptures gracefully oscillating with natural air currents and precision counterweights.", "The Wind Pavilion", 20, 50),
    ("Retrofuturism: Sci-Fi Poster Art of the 1970s", "Art & Exhibitions", "Airbrushed space colonies, synth covers, and chrome spaceships by legendary sci-fi illustrators.", "Cyber Art Space", 15, 40),
    ("Textile Tapestries: Natural Dye Weaving", "Art & Exhibitions", "Hand-spun wool tapestries dyed with madder root, indigo, and marigolds by indigenous artisan weavers.", "Weaver Collective Hall", 20, 45),
    ("Glass & Fire: Venetian Blown Sculptures", "Art & Exhibitions", "Molten glass blown into transparent oceanic jellyfish, translucent vases, and vibrant rainbow chandeliers.", "Glassworks Studio", 25, 60),
    ("Street Murals: Urban Culture & Stencil Retrospective", "Art & Exhibitions", "Reconstructed street walls, aerosol canvases, and iconic guerrilla stencils by international street artists.", "Underpass Art Vault", 15, 40),
    ("Surrealist Dreams: Oil Paintings on Wood", "Art & Exhibitions", "Melting clocks, floating bowler hats, and mysterious labyrinth doorways painted in meticulous classical realism.", "Surreal Gallery East", 20, 50),
    ("Architectural Models: Sustainable Cities 2050", "Art & Exhibitions", "Intricate 3D-printed wooden scale models of vertical forest towers, tidal power stations, and zero-carbon hubs.", "Architecture School Wing", 15, 35),
    ("Portraits of Resilience: Documentary Photo", "Art & Exhibitions", "Award-winning photojournalism portraits honoring high-altitude Himalayan goat shepherds and artisan weavers.", "Humanity Center Gallery", 10, 30),
    ("Neon Nights: Glass Tube Art Installations", "Art & Exhibitions", "Custom hand-bent glowing argon and neon gas typography filling a pitch-black labyrinth room.", "The Neon Labyrinth", 25, 55),

    # Workshops & Conferences (14 templates)
    ("Hand-Building Pottery & Glaze Masterclass", "Workshops", "Shape your own stoneware ramen bowls on the wheel, carve foot rings, and apply studio reactive glazes.", "Clay & Kiln Studio", 35, 75),
    ("Specialty Coffee Pour-Over & V60 Brewing", "Workshops", "Dial in grind size, water chemistry, flow rates, and brew temperatures to unlock floral notes in light roasts.", "Coffee Lab Sector 10", 25, 50),
    ("Leathercraft: Stitching a Handcrafted Wallet", "Workshops", "Saddle-stitch full-grain vegetable-tanned leather, bevel raw edges, and burnish beeswax seams by hand.", "Maker Studio Woodshop", 40, 85),
    ("Cyanotype Printing: Sunlight Solar Photography", "Workshops", "Coat cotton paper with UV-sensitive emulsion, place botanical ferns, and develop rich Prussian blue prints in water.", "Artisan Sun Terrace", 20, 45),
    ("Analog Synth Patching: Voltage & Oscillators", "Workshops", "Learn subtractive synthesis, patch modular cables, modulate LFOs, and shape fat analog basslines from scratch.", "Sound Lab Studio C", 30, 65),
    ("Perfume Alchemy: Formulating Custom Scents", "Workshops", "Balance top, heart, and base notes using rare botanical essences, bergamot, sandalwood, and amber resins.", "Aromatics Atelier", 50, 110),
    ("Woodblock Relief Printing on Hand-Made Paper", "Workshops", "Carve gouge designs into Japanese shina plywood and pull limited-edition linocut prints using oil inks.", "Print Studio 2", 25, 55),
    ("Artisan Sourdough: Starter to Loaf Intensive", "Workshops", "Hydration percentages, stretch-and-fold timing, banneton scoring, and baking in heavy cast iron Dutch ovens.", "The Flour Lab", 35, 80),
    ("UI/UX Design Systems in Figma Masterclass", "Workshops", "Build scalable design tokens, auto-layout responsive components, and interactive prototypes for design teams.", "Design Guild Lab", 30, 70),
    ("Urban Gardening: Microgreens & Balcony Herbs", "Workshops", "Grow nutrient-dense radish microgreens, companion plant culinary herbs, and master indoor LED grow lights.", "Greenhouse Sector 1", 20, 45),
    ("Cocktail Mixology: Bitters, Syrups & Balance", "Workshops", "Shake classic sours, clarify milk punches, infuse botanical syrups, and master proper ice carving techniques.", "Speakeasy Bar Lab", 45, 95),
    ("Smartphone Cinematography & Color Grading", "Workshops", "Log picture profiles, gimbal movements, three-point lighting setups, and DaVinci Resolve color grading.", "Media Hub Lab 3", 30, 65),
    ("Mindfulness Meditation & Sound Bath Ceremony", "Workshops", "Tibetan singing bowls, planetary gongs, and breathwork guidance to calm the nervous system in a quiet dome.", "Serenity Shala", 25, 50),
    ("Bookbinding Atelier: Japanese Stab Binding", "Workshops", "Foliate archival rag paper, punch needle holes, and hand-bind beautiful exposed-spine thread notebooks.", "Paper Studio North", 25, 55),
]

class Command(BaseCommand):
    help = 'Seeds approximately 100 realistic, beautiful events in the SQLite database with images, users, tiers, and bookmarks.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear previously created dummy events before seeding',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("🚀 Starting 100-event seeding process..."))

        if options.get('clear'):
            self.stdout.write("Clearing existing events...")
            Event.objects.all().delete()

        # 1. Create or ensure Organizers exist
        organizer_users = []
        for org_data in ORGANIZERS_DATA:
            user, created = User.objects.get_or_create(
                email=org_data['email'],
                defaults={
                    'full_name': org_data['name'],
                    'role': 'manager',
                    'is_staff': True,
                    'city': 'Chandigarh',
                    'avatar_url': org_data['logo'],
                }
            )
            user.set_password('password123')
            user.role = 'manager'
            user.save()
            organizer_users.append(user)

            # Profile
            OrganizerProfile.objects.get_or_create(
                user=user,
                defaults={
                    'organization_name': org_data['org_name'],
                    'handle': org_data['handle'],
                    'bio': org_data['bio'],
                    'website': org_data['website'],
                    'instagram': org_data['instagram'],
                    'logo_url': org_data['logo'],
                    'support_email': org_data['email'],
                }
            )

        self.stdout.write(self.style.SUCCESS(f"✅ Prepared {len(organizer_users)} organizer accounts."))

        # 2. Create or ensure Attendee Users exist
        attendee_users = []
        for att in ATTENDEES_DATA:
            user, created = User.objects.get_or_create(
                email=att['email'],
                defaults={
                    'full_name': att['name'],
                    'role': 'user',
                    'city': att['city'],
                }
            )
            user.set_password('password123')
            user.save()
            attendee_users.append(user)

        main_user = attendee_users[0]  # user@evento.com
        self.stdout.write(self.style.SUCCESS(f"✅ Prepared {len(attendee_users)} attendee accounts."))

        # 3. Create exactly 100 events
        base_date = date.today()
        created_count = 0
        total_target = 100
        templates_count = len(EVENT_TEMPLATES)

        # Shuffle templates for good distribution
        rng = random.Random(42)  # Deterministic seed for consistency
        all_specs = []

        for i in range(total_target):
            tmpl_idx = i % templates_count
            title_base, category, desc, venue_base, min_p, max_p = EVENT_TEMPLATES[tmpl_idx]

            # If template reused, give it an edition/chapter suffix
            iteration = i // templates_count
            if iteration == 0:
                title = title_base
            elif iteration == 1:
                title = f"{title_base} (Winter Edition)"
            else:
                title = f"{title_base} (Vol. {iteration + 1})"

            # Randomize date: upcoming 1 to 180 days out, plus a few past events
            if i % 15 == 0 and i > 0:
                event_date = base_date - timedelta(days=rng.randint(3, 40))
                status = 'past'
            else:
                event_date = base_date + timedelta(days=rng.randint(2, 160))
                status = 'published'

            city = CITIES[i % len(CITIES)]
            venue = f"{venue_base} • Sector {rng.randint(1, 45)}" if 'Chandigarh' in city or 'Mohali' in city else f"{venue_base}, {city}"
            address = f"{venue}, {city}, India"

            # Image selection from appropriate pool
            pool = UNSPLASH_POOLS.get(category, UNSPLASH_POOLS['Music & Concerts'])
            image_url = pool[i % len(pool)]

            # Curated hero/recommended highlights
            is_hero = (i in [0, 4, 12, 22, 35])
            is_recommended = (i in [1, 3, 7, 14, 18, 25, 30, 42, 50, 65, 80])
            is_featured = (i % 6 == 0)

            taglines = [
                'Selling Fast across the region',
                'Exclusive One-Night-Only Stage Showcase',
                'Curated Live Production & Audio Design',
                'Featured in Weekend Cultural Highlights',
                'Limited Early-Bird Passes Available',
            ]
            tagline = rng.choice(taglines) if (is_hero or is_recommended) else ''
            badge = rng.choice(['Top Pick', 'Trending', 'Selling Out', 'Editor’s Choice']) if is_recommended else ''

            start_hour = rng.choice([10, 11, 14, 16, 18, 19, 20, 21])
            start_time_val = time(start_hour, rng.choice([0, 30]))
            end_time_val = time((start_hour + rng.randint(3, 5)) % 24, 0)

            organizer = organizer_users[i % len(organizer_users)]

            event, created = Event.objects.get_or_create(
                title=title,
                defaults={
                    'organizer': organizer,
                    'category': category,
                    'description': desc,
                    'banner_image': image_url,
                    'date': event_date,
                    'start_time': start_time_val,
                    'end_time': end_time_val,
                    'venue_name': venue,
                    'city': city,
                    'address': address,
                    'is_online': (i % 18 == 0),
                    'status': status,
                    'is_featured': is_featured,
                    'is_banner_hero': is_hero,
                    'banner_tagline': tagline,
                    'banner_cta_text': 'Book Passes' if not is_hero else 'Reserve Front Row',
                    'banner_priority': 100 - i if is_hero else 0,
                    'is_recommended': is_recommended,
                    'recommendation_badge': badge,
                    'has_assigned_seating': False,
                }
            )

            if created:
                created_count += 1

            # Ensure ticket tiers exist
            if not event.tiers.exists():
                # Tier 1: General
                TicketTier.objects.create(
                    event=event,
                    name='General Admission',
                    price=Decimal(str(min_p)),
                    capacity=rng.randint(80, 300),
                    sold_count=rng.randint(5, 50),
                    description='Standard entrance pass with full stage viewing access.',
                )
                # Tier 2: VIP / Early Bird
                if max_p > min_p:
                    TicketTier.objects.create(
                        event=event,
                        name='VIP Priority Access',
                        price=Decimal(str(max_p)),
                        capacity=rng.randint(25, 80),
                        sold_count=rng.randint(2, 20),
                        description='Fast-track entry lane, lounge access, and complimentary refreshments.',
                    )
                # Tier 3: Occasional Student / Early release
                if i % 3 == 0:
                    TicketTier.objects.create(
                        event=event,
                        name='Early Bird Pass',
                        price=Decimal(str(max(0, min_p - 10))),
                        capacity=rng.randint(40, 100),
                        sold_count=rng.randint(10, 40),
                        description='Discounted early admission pass for first 50 buyers.',
                    )

            # Add Saved Events for user@evento.com (save ~14 varied events)
            if i in [0, 1, 3, 5, 8, 12, 17, 24, 31, 40, 52, 68, 85]:
                SavedEvent.objects.get_or_create(user=main_user, event=event)

            # Random likes
            for att_user in rng.sample(attendee_users, k=rng.randint(1, min(6, len(attendee_users)))):
                EventLike.objects.get_or_create(user=att_user, event=event)

        self.stdout.write(self.style.SUCCESS(f"🎉 Successfully seeded events! Total events in DB: {Event.objects.count()} (Created {created_count} new events)."))
        self.stdout.write(self.style.SUCCESS(f"🔖 Saved events for {main_user.email}: {SavedEvent.objects.filter(user=main_user).count()}"))
        self.stdout.write(self.style.SUCCESS("All events include high-resolution banner images, ticket tiers, and categories."))
