/**
 * Carreta Verde - Harvest Data
 * Las 4 cosechas de miel con su carácter único
 */

export interface Harvest {
  id: string;
  name: string;
  season: 'primavera' | 'verano' | 'otoño' | 'invierno';
  shortName: string;
  color: string;
  colorLight: string;
  months: string;
  description: string;
  flavorNotes: string[];
  floralOrigin: string[];
  pairings: string[];
  characteristics: {
    sweetness: number;
    intensity: number;
    crystallization: 'rápida' | 'media' | 'lenta';
    texture: string;
  };
  available: boolean;
  limitedEdition?: boolean;
}

export interface ProductSize {
  id: string;
  name: string;
  grams: number;
  price: number;
  comparePrice?: number;
}

export const PRODUCT_SIZES: ProductSize[] = [
  { id: 'mini', name: 'Mini', grams: 150, price: 89 },
  { id: 'regular', name: 'Regular', grams: 350, price: 169 },
  { id: 'familiar', name: 'Familiar', grams: 500, price: 229, comparePrice: 259 },
  { id: 'grande', name: 'Grande', grams: 1000, price: 399, comparePrice: 458 },
];

export const HARVESTS: Harvest[] = [
  {
    id: 'primavera',
    name: 'Cosecha de Primavera',
    season: 'primavera',
    shortName: 'Primavera',
    color: '#7CB342',
    colorLight: '#C5E1A5',
    months: 'Marzo - Mayo',
    description: 'Nuestra cosecha más suave y floral. Las abejas recolectan el néctar de las primeras flores de la temporada.',
    flavorNotes: ['Floral suave', 'Cítricos', 'Herbal fresco'],
    floralOrigin: ['Dzizilché', 'Tajonal', 'Flores silvestres'],
    pairings: ['Té verde', 'Quesos frescos', 'Ensaladas', 'Yogurt'],
    characteristics: {
      sweetness: 3,
      intensity: 2,
      crystallization: 'lenta',
      texture: 'Líquida y ligera',
    },
    available: true,
  },
  {
    id: 'verano',
    name: 'Cosecha de Verano',
    season: 'verano',
    shortName: 'Verano',
    color: '#FFB300',
    colorLight: '#FFE082',
    months: 'Junio - Agosto',
    description: 'El sol intenso produce nuestra miel más robusta. Sabores complejos y profundos.',
    flavorNotes: ['Frutal tropical', 'Madera dulce', 'Caramelo'],
    floralOrigin: ['Chakah', 'Tsalam', 'Jabín'],
    pairings: ['Carnes asadas', 'Quesos curados', 'Pan artesanal'],
    characteristics: {
      sweetness: 5,
      intensity: 4,
      crystallization: 'media',
      texture: 'Densa y untuosa',
    },
    available: true,
  },
  {
    id: 'otono',
    name: 'Cosecha de Otoño',
    season: 'otoño',
    shortName: 'Otoño',
    color: '#E65100',
    colorLight: '#FFCC80',
    months: 'Sep - Nov',
    description: 'Las lluvias traen una segunda floración. Equilibrio perfecto entre dulzura y complejidad.',
    flavorNotes: ['Ámbar', 'Especias suaves', 'Miel de flores'],
    floralOrigin: ['Xtabentún', 'Box Katsim', 'Huano'],
    pairings: ['Té chai', 'Avena', 'Nueces', 'Helado'],
    characteristics: {
      sweetness: 4,
      intensity: 3,
      crystallization: 'media',
      texture: 'Cremosa',
    },
    available: true,
  },
  {
    id: 'invierno',
    name: 'Cosecha de Invierno',
    season: 'invierno',
    shortName: 'Invierno',
    color: '#6D4C41',
    colorLight: '#D7CCC8',
    months: 'Dic - Feb',
    description: 'Edición limitada. La cosecha más escasa y preciada del año.',
    flavorNotes: ['Madera ahumada', 'Melaza', 'Notas balsámicas'],
    floralOrigin: ['Tzitzilché', 'Chakté', 'Bosque seco'],
    pairings: ['Café', 'Whisky', 'Chocolate amargo'],
    characteristics: {
      sweetness: 4,
      intensity: 5,
      crystallization: 'rápida',
      texture: 'Cristalina granulada',
    },
    available: true,
    limitedEdition: true,
  },
];
