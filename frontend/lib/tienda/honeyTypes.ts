/**
 * Carreta Verde - Honey Types Data
 * Los 4 tipos de miel por origen floral
 */

export interface HoneyImage {
  id: string;
  url: string;
  alt: string;
  type: 'jar' | 'texture' | 'drip' | 'origin' | 'pairing';
}

export interface HoneyType {
  id: string;
  name: string;
  shortName: string;
  floralOrigin: string;
  color: string;
  colorLight: string;
  colorDark: string;
  description: string;
  longDescription: string;
  flavorNotes: string[];
  aromas: string[];
  pairings: string[];
  regions: string[];
  characteristics: {
    sweetness: number;
    intensity: number;
    crystallization: 'rápida' | 'media' | 'lenta';
    texture: string;
    color: string;
  };
  images: HoneyImage[];
  available: boolean;
  nextHarvest?: string;
  bestSeller?: boolean;
  seasonal?: boolean;
}

export interface ProductSize {
  id: string;
  name: string;
  grams: number;
  price: number;
  comparePrice?: number;
  availableStandalone?: boolean; // Si false, solo disponible en bundles
  amazonSKU?: string; // SKU para Amazon FBA/MCF
  recommended?: boolean; // Badge de "Mejor Valor"
}

export const PRODUCT_SIZES: ProductSize[] = [
  {
    id: 'regular',
    name: '330g',
    grams: 330,
    price: 86,
    availableStandalone: false, // SOLO EN BUNDLES
  },
  {
    id: 'familiar',
    name: '580g',
    grams: 580,
    price: 143,
    availableStandalone: true,
    amazonSKU: 'CV-580',
  },
  {
    id: 'grande',
    name: '1100g (Mejor Valor)',
    grams: 1100,
    price: 241,
    comparePrice: 286, // Equivalente a 2×580g
    availableStandalone: true,
    amazonSKU: 'CV-1100',
    recommended: true,
  },
];

export const HONEY_TYPES: HoneyType[] = [
  // === DISPONIBLES (primero) ===
  {
    id: 'aceitilla',
    name: 'Miel de Flor de Aceitilla',
    shortName: 'Aceitilla',
    floralOrigin: 'Flor de Aceitilla',
    color: '#FBC02D',
    colorLight: '#FFF9C4',
    colorDark: '#F9A825',
    description: 'Brillante y equilibrada. La más versátil de nuestra colección.',
    longDescription: 'La aceitilla es una flor silvestre que crece en el altiplano mexicano. Su miel tiene un color dorado brillante y un sabor equilibrado que combina notas florales con un toque herbáceo. Es nuestra miel más versátil.',
    flavorNotes: ['Floral herbáceo', 'Mantequilla', 'Toque herbal'],
    aromas: ['Flores silvestres', 'Pradera', 'Miel clásica'],
    pairings: ['Pan caliente', 'Avena', 'Postres', 'Aderezos'],
    regions: ['Zacatecas'],
    characteristics: {
      sweetness: 4,
      intensity: 3,
      crystallization: 'media',
      texture: 'Cremosa suave',
      color: 'Dorado brillante',
    },
    images: [
      { id: 'jar-1', url: '/tienda/miel-aceitilla.jpg', alt: 'Tarro de miel de aceitilla Carreta Verde', type: 'jar' },
      { id: 'texture-1', url: 'https://images.unsplash.com/photo-1558642452-9d2a7deb7f62?w=800&q=90', alt: 'Textura dorada cremosa', type: 'texture' },
      { id: 'drip-1', url: 'https://images.unsplash.com/photo-1471943311424-646960669fbc?w=800&q=90', alt: 'Miel dorada fluyendo', type: 'drip' },
      { id: 'origin-1', url: 'https://images.unsplash.com/photo-1490750967868-88aa4486c946?w=800&q=90', alt: 'Campo de aceitilla', type: 'origin' },
    ],
    available: true,
  },
  {
    id: 'multifloral',
    name: 'Miel Multifloral de Monte',
    shortName: 'Multifloral',
    floralOrigin: 'Flores Silvestres del Monte',
    color: '#1976D2',
    colorLight: '#BBDEFB',
    colorDark: '#0D47A1',
    description: 'Compleja y única. Cada lote cuenta una historia diferente.',
    longDescription: 'Nuestra miel multifloral proviene de los montes de Jalisco, donde las abejas recolectan néctar de docenas de flores silvestres. Cada lote es único, reflejando la biodiversidad de la región y la época del año.',
    flavorNotes: ['Floral complejo', 'Frutal', 'Especias suaves'],
    aromas: ['Bosque', 'Flores mixtas', 'Hierba fresca'],
    pairings: ['Café', 'Helado', 'Fruta fresca', 'Granola'],
    regions: ['Jalisco'],
    characteristics: {
      sweetness: 4,
      intensity: 4,
      crystallization: 'lenta',
      texture: 'Variable cada lote',
      color: 'Ámbar variable',
    },
    images: [
      { id: 'jar-1', url: '/tienda/miel-multifloral.jpg', alt: 'Tarro de miel multifloral Carreta Verde', type: 'jar' },
      { id: 'texture-1', url: 'https://images.unsplash.com/photo-1558642452-9d2a7deb7f62?w=800&q=90', alt: 'Textura rica variada', type: 'texture' },
      { id: 'drip-1', url: 'https://images.unsplash.com/photo-1471943311424-646960669fbc?w=800&q=90', alt: 'Miel fluyendo', type: 'drip' },
      { id: 'origin-1', url: 'https://images.unsplash.com/photo-1469474968028-56623f02e42e?w=800&q=90', alt: 'Monte de Jalisco', type: 'origin' },
    ],
    available: true,
    seasonal: true,
  },

  // === AGOTADOS (al final) ===
  {
    id: 'azahar',
    name: 'Miel de Flor de Azahar',
    shortName: 'Azahar',
    floralOrigin: 'Flor de Naranjo',
    color: '#FF9800',
    colorLight: '#FFE0B2',
    colorDark: '#E65100',
    description: 'Aromática y delicada. El aroma inconfundible del azahar.',
    longDescription: 'La flor de azahar, del naranjo, produce una miel con un aroma floral intenso y distintivo. Su sabor es suave con notas cítricas sutiles. Es especialmente apreciada por su fragancia única que evoca los huertos de cítricos.',
    flavorNotes: ['Cítrico suave', 'Floral intenso', 'Notas de naranja'],
    aromas: ['Azahar', 'Cítricos', 'Flores blancas'],
    pairings: ['Té', 'Postres', 'Quesos suaves', 'Yogurt'],
    regions: ['Veracruz', 'San Luis Potosí'],
    characteristics: {
      sweetness: 4,
      intensity: 3,
      crystallization: 'lenta',
      texture: 'Líquida sedosa',
      color: 'Ámbar claro',
    },
    images: [
      { id: 'jar-1', url: '/tienda/miel-azahar.jpg', alt: 'Tarro de miel de azahar Carreta Verde', type: 'jar' },
      { id: 'texture-1', url: 'https://images.unsplash.com/photo-1558642452-9d2a7deb7f62?w=800&q=90', alt: 'Textura líquida dorada', type: 'texture' },
      { id: 'drip-1', url: 'https://images.unsplash.com/photo-1471943311424-646960669fbc?w=800&q=90', alt: 'Miel de azahar fluyendo', type: 'drip' },
      { id: 'origin-1', url: 'https://images.unsplash.com/photo-1464226184884-fa280b87c399?w=800&q=90', alt: 'Huerto de naranjos', type: 'origin' },
    ],
    available: false,
    nextHarvest: 'Abr 2026',
    bestSeller: true,
  },
  {
    id: 'mezquite',
    name: 'Miel de Flor de Mezquite',
    shortName: 'Mezquite',
    floralOrigin: 'Flor de Mezquite',
    color: '#795548',
    colorLight: '#D7CCC8',
    colorDark: '#4E342E',
    description: 'Intensa y profunda. Notas ahumadas del desierto norteño.',
    longDescription: 'El mezquite es un árbol emblemático del norte de México. Su miel tiene un color oscuro característico y un sabor intenso con notas que recuerdan al caramelo y un toque ahumado. Es la más robusta de nuestra colección.',
    flavorNotes: ['Caramelo', 'Notas ahumadas', 'Madera'],
    aromas: ['Tierra', 'Madera de mezquite', 'Caramelo oscuro'],
    pairings: ['Carnes', 'BBQ', 'Quesos añejos', 'Pan de centeno'],
    regions: ['Durango', 'Chihuahua', 'Coahuila'],
    characteristics: {
      sweetness: 3,
      intensity: 5,
      crystallization: 'rápida',
      texture: 'Densa cremosa',
      color: 'Ámbar oscuro',
    },
    images: [
      { id: 'jar-1', url: '/tienda/miel-mezquite.jpg', alt: 'Tarro de miel de mezquite Carreta Verde', type: 'jar' },
      { id: 'texture-1', url: 'https://images.unsplash.com/photo-1558642452-9d2a7deb7f62?w=800&q=90', alt: 'Textura densa oscura', type: 'texture' },
      { id: 'drip-1', url: 'https://images.unsplash.com/photo-1471943311424-646960669fbc?w=800&q=90', alt: 'Miel oscura fluyendo', type: 'drip' },
      { id: 'origin-1', url: 'https://images.unsplash.com/photo-1509316785289-025f5b846b35?w=800&q=90', alt: 'Desierto con mezquites', type: 'origin' },
    ],
    available: false,
    nextHarvest: 'Mar 2026',
  },
];
