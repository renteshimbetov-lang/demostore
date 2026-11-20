import asyncio
import os
import json
from dotenv import load_dotenv
load_dotenv('/home/ubuntu/demostore/.env')
import asyncpg

CATEGORIES = [
    (1, 'Smartfonlar', 'smartphone'),
    (2, 'Noutbuklar', 'laptop'),
    (3, 'Quloqchinlar va Audio', 'headphones'),
    (4, 'Aqlli soatlar', 'watch'),
    (5, 'Aksessuarlar', 'plug'),
]

PRODUCTS = [
    {
        'id': 12,
        'category_id': 1,
        'name': 'iPhone 16 Pro (128GB / Black Titanium)',
        'description': 'A18 Pro chipi, Titanium korpus, 48MP yangilangan kamera tizimi va Camera Control tugmasi. 100% ideal holatda.',
        'price': 980,
        'currency': 'USD',
        'price_uzs': 12544000,
        'image_url': '/static/products/prod_12.jpg',
        'gallery_images': json.dumps(['/static/products/prod_12.jpg', '/static/gallery/prod_12_photo_1.jpg', '/static/gallery/prod_12_photo_2.jpg']),
        'is_active': 1,
        'is_available': 1,
        'views_count': 142
    },
    {
        'id': 13,
        'category_id': 1,
        'name': 'iPhone 16 Pro Max (256GB / Natural Titanium)',
        'description': 'Eng yirik 6.9" Super Retina XDR ekran, A18 Pro protsessor va 5x optik zoom. Yangi qutida.',
        'price': 1190,
        'currency': 'USD',
        'price_uzs': 15232000,
        'image_url': '/static/products/prod_13.jpg',
        'gallery_images': json.dumps(['/static/products/prod_13.jpg', '/static/gallery/prod_13_photo_1.jpg', '/static/gallery/prod_13_photo_2.jpg']),
        'is_active': 1,
        'is_available': 1,
        'views_count': 230
    },
    {
        'id': 14,
        'category_id': 1,
        'name': 'iPhone 15 Pro Max (256GB / Blue Titanium)',
        'description': 'A17 Pro protsessor, titan rom va Action Button. Batareya holati 95%, original.',
        'price': 890,
        'currency': 'USD',
        'price_uzs': 11392000,
        'image_url': '/static/products/prod_14.jpg',
        'gallery_images': json.dumps(['/static/products/prod_14.jpg', '/static/gallery/prod_14_photo_1.jpg', '/static/gallery/prod_14_photo_2.jpg']),
        'is_active': 1,
        'is_available': 1,
        'views_count': 88
    },
    {
        'id': 15,
        'category_id': 1,
        'name': 'iPhone 15 Pro (128GB / White Titanium)',
        'description': 'Kompakt o\'lcham, A17 Pro, 120Hz ProMotion ekran. Hech qanday tirnalishsiz.',
        'price': 760,
        'currency': 'USD',
        'price_uzs': 9728000,
        'image_url': '/static/products/prod_15.jpg',
        'gallery_images': json.dumps(['/static/products/prod_15.jpg', '/static/gallery/prod_15_photo_1.jpg']),
        'is_active': 1,
        'is_available': 1,
        'views_count': 94
    },
    {
        'id': 16,
        'category_id': 1,
        'name': 'iPhone 14 Pro Max (128GB / Deep Purple)',
        'description': 'Dynamic Island, 48MP asosiy kamera, Always-On ekran. Batareya 88%.',
        'price': 690,
        'currency': 'USD',
        'price_uzs': 8832000,
        'image_url': '/static/products/prod_16.jpg',
        'gallery_images': json.dumps(['/static/products/prod_16.jpg', '/static/gallery/prod_16_photo_1.jpg']),
        'is_active': 1,
        'is_available': 1,
        'views_count': 112
    },
    {
        'id': 17,
        'category_id': 1,
        'name': 'iPhone 13 Pro (128GB / Sierra Blue)',
        'description': 'A15 Bionic, 120Hz displey, 3 talik kamera tizimi. Juda toza holatda.',
        'price': 520,
        'currency': 'USD',
        'price_uzs': 6656000,
        'image_url': '/static/products/prod_17.jpg',
        'gallery_images': json.dumps(['/static/products/prod_17.jpg', '/static/gallery/prod_17_photo_1.jpg']),
        'is_active': 1,
        'is_available': 1,
        'views_count': 76
    },
    {
        'id': 18,
        'category_id': 1,
        'name': 'iPhone Air (256GB / Black / 100%)',
        'description': 'Yengil, nozik korpusli yangi model. 256GB xotira va 100% batareya salomatligi.',
        'price': 850,
        'currency': 'USD',
        'price_uzs': 10880000,
        'image_url': '/static/products/prod_18.jpg',
        'gallery_images': json.dumps(['/static/products/prod_18.jpg']),
        'is_active': 1,
        'is_available': 1,
        'views_count': 64
    },
    {
        'id': 19,
        'category_id': 2,
        'name': 'MacBook Air 13" M3 16/512GB (Midnight)',
        'description': 'Apple M3 chipi, 16GB birlashgan xotira, 512GB SSD. 18 soat batareya avtonomligi, yengil vazn.',
        'price': 1250,
        'currency': 'USD',
        'price_uzs': 16000000,
        'image_url': '/static/products/prod_19.jpg',
        'gallery_images': json.dumps(['/static/products/prod_19.jpg']),
        'is_active': 1,
        'is_available': 1,
        'views_count': 310
    },
    {
        'id': 22,
        'category_id': 4,
        'name': 'Apple Watch Ultra 2 (49mm Titanium)',
        'description': 'Ekstremal sharoitlar uchun titan korpus, 3000 nit eng yorqin ekran, Action tugmasi.',
        'price': 690,
        'currency': 'USD',
        'price_uzs': 8832000,
        'image_url': '/static/products/prod_22.jpg',
        'gallery_images': json.dumps(['/static/products/prod_22.jpg']),
        'is_active': 1,
        'is_available': 1,
        'views_count': 85
    },
    {
        'id': 23,
        'category_id': 3,
        'name': 'AirPods Pro 2 (USB-C Case)',
        'description': 'Aktiv shovqin bekor qilish (ANC) 2x kuchli, Shaffof rejim, Type-C zaryadka.',
        'price': 210,
        'currency': 'USD',
        'price_uzs': 2688000,
        'image_url': '/static/products/prod_23.jpg',
        'gallery_images': json.dumps(['/static/products/prod_23.jpg']),
        'is_active': 1,
        'is_available': 1,
        'views_count': 175
    },
    {
        'id': 25,
        'category_id': 5,
        'name': 'Apple 20W USB-C Power Adapter (Original)',
        'description': 'Original tezkor zaryadlash bloki, barcha iPhone va iPad modellari uchun tavsiya etiladi.',
        'price': 25,
        'currency': 'USD',
        'price_uzs': 320000,
        'image_url': '/static/products/prod_25.jpg',
        'gallery_images': json.dumps(['/static/products/prod_25.jpg']),
        'is_active': 1,
        'is_available': 1,
        'views_count': 45
    },
    {
        'id': 26,
        'category_id': 5,
        'name': 'Apple USB-C to USB-C Woven Cable (1m)',
        'description': 'Mustahkam to\'qima qoplamali Type-C kabeli, tezkor quvvatlash va fayl uzatishni qo\'llab-quvvatlaydi.',
        'price': 20,
        'currency': 'USD',
        'price_uzs': 256000,
        'image_url': '/static/products/prod_26.jpg',
        'gallery_images': json.dumps(['/static/products/prod_26.jpg']),
        'is_active': 1,
        'is_available': 1,
        'views_count': 32
    },
    {
        'id': 27,
        'category_id': 1,
        'name': 'iPhone 16 Pro Max (256GB / Desert Titanium)',
        'description': 'Yangi Desert Titanium rangi, eng kuchli kamera va batareya. 100% yangi holatda.',
        'price': 1220,
        'currency': 'USD',
        'price_uzs': 15616000,
        'image_url': '/static/products/prod_27.jpg',
        'gallery_images': json.dumps(['/static/products/prod_27.jpg']),
        'is_active': 1,
        'is_available': 1,
        'views_count': 410
    },
    {
        'id': 30,
        'category_id': 1,
        'name': 'iPhone 15 Pro Max (256GB / Black Titanium)',
        'description': 'Titan korpus, A17 Pro chip, 5x telephoto kamera. Qora rang, ideal holat.',
        'price': 890,
        'currency': 'USD',
        'price_uzs': 11392000,
        'image_url': '/static/products/prod_30.jpg',
        'gallery_images': json.dumps(['/static/products/prod_30.jpg']),
        'is_active': 1,
        'is_available': 1,
        'views_count': 195
    }
]

async def seed():
    db_url = os.getenv('DATABASE_URL')
    print('Connecting to AWS RDS PostgreSQL...')
    conn = await asyncpg.connect(db_url, ssl='require')

    # Categories
    for cid, name, icon in CATEGORIES:
        await conn.execute('''
            INSERT INTO categories (id, name, icon)
            VALUES ($1, $2, $3)
            ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, icon = EXCLUDED.icon;
        ''', cid, name, icon)
    print(f'Inserted/Updated {len(CATEGORIES)} categories.')

    # Products
    for p in PRODUCTS:
        await conn.execute('''
            INSERT INTO products (
                id, category_id, name, description, price, currency, price_uzs,
                image_url, gallery_images, is_active, is_available, views_count
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12
            )
            ON CONFLICT (id) DO UPDATE SET
                category_id = EXCLUDED.category_id,
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                price = EXCLUDED.price,
                currency = EXCLUDED.currency,
                price_uzs = EXCLUDED.price_uzs,
                image_url = EXCLUDED.image_url,
                gallery_images = EXCLUDED.gallery_images,
                is_active = EXCLUDED.is_active,
                is_available = EXCLUDED.is_available,
                views_count = EXCLUDED.views_count;
        ''', p['id'], p['category_id'], p['name'], p['description'], p['price'], p['currency'], p['price_uzs'], p['image_url'], p['gallery_images'], p['is_active'], p['is_available'], p['views_count'])

    print(f'Inserted/Updated {len(PRODUCTS)} products into AWS RDS PostgreSQL!')
    await conn.close()

if __name__ == '__main__':
    asyncio.run(seed())
