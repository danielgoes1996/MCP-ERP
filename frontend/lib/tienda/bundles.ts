/**
 * Carreta Verde - Bundle Products
 * Productos exclusivos de la tienda (no disponibles en Amazon)
 */

export interface Bundle {
  id: string;
  name: string;
  shortName: string;
  description: string;
  longDescription: string;
  items: {
    honeyTypeId: string;
    sizeId: string;
    quantity: number;
  }[];
  price: number;
  comparePrice: number; // Precio si se comprara por separado
  savings: number;
  badge?: string;
  imageUrl?: string;
  exclusive: boolean;
}

export const BUNDLES: Bundle[] = [
  {
    id: 'pack-4-cosechas',
    name: 'Pack Las 4 Cosechas',
    shortName: 'Las 4 Cosechas',
    description: 'Descubre todos nuestros sabores en formato ideal para probar',
    longDescription: 'El pack perfecto para conocer la diversidad de sabores de la miel mexicana. Incluye las 4 variedades en frascos de 330g cada uno: Aceitilla, Multifloral, Azahar y Mezquite. Total: 1,320g de miel premium.',
    items: [
      { honeyTypeId: 'aceitilla', sizeId: 'regular', quantity: 1 },
      { honeyTypeId: 'multifloral', sizeId: 'regular', quantity: 1 },
      { honeyTypeId: 'azahar', sizeId: 'regular', quantity: 1 },
      { honeyTypeId: 'mezquite', sizeId: 'regular', quantity: 1 },
    ],
    price: 300,
    comparePrice: 344, // 4 × $86
    savings: 44,
    badge: 'Exclusivo Tienda',
    exclusive: true,
  },
  {
    id: 'pack-disponibles',
    name: 'Pack Cosechas Disponibles',
    shortName: 'Pack 2 Disponibles',
    description: 'Aceitilla + Multifloral en tamaño regular',
    longDescription: 'Las dos cosechas actualmente disponibles en formato 330g. Perfecto para probar antes de comprometerte con tamaños más grandes.',
    items: [
      { honeyTypeId: 'aceitilla', sizeId: 'regular', quantity: 1 },
      { honeyTypeId: 'multifloral', sizeId: 'regular', quantity: 1 },
    ],
    price: 160,
    comparePrice: 172, // 2 × $86
    savings: 12,
    badge: 'Pack de Prueba',
    exclusive: true,
  },
  {
    id: 'pack-familiar',
    name: 'Pack Familiar Duo',
    shortName: 'Pack Familiar',
    description: 'Prueba 2 sabores diferentes en tamaño familiar',
    longDescription: 'Dos frascos de 580g de sabores diferentes. Elige tus favoritos y disfruta por más tiempo. Ideal para familias o para quienes ya conocen sus preferencias.',
    items: [
      // Se configuran dinámicamente al agregar al carrito
      { honeyTypeId: 'aceitilla', sizeId: 'familiar', quantity: 1 },
      { honeyTypeId: 'multifloral', sizeId: 'familiar', quantity: 1 },
    ],
    price: 260,
    comparePrice: 286, // 2 × $143
    savings: 26,
    badge: 'Ahorra 9%',
    exclusive: true,
  },
  {
    id: 'pack-grande-duo',
    name: 'Pack Grande Premium',
    shortName: 'Pack Premium',
    description: 'Dos frascos de 1.1kg - El mejor valor',
    longDescription: 'Nuestro pack de mayor valor. Dos frascos grandes (1.1kg cada uno) de tus sabores favoritos. Perfecto para familias grandes o consumidores frecuentes. Total: 2.2kg de miel premium.',
    items: [
      { honeyTypeId: 'aceitilla', sizeId: 'grande', quantity: 1 },
      { honeyTypeId: 'multifloral', sizeId: 'grande', quantity: 1 },
    ],
    price: 450,
    comparePrice: 482, // 2 × $241
    savings: 32,
    badge: 'Mejor Valor',
    exclusive: true,
  },
];

// Helper para calcular precio de bundle
export function calculateBundleValue(bundle: Bundle): {
  totalValue: number;
  savings: number;
  savingsPercent: number;
} {
  const totalValue = bundle.comparePrice;
  const savings = bundle.comparePrice - bundle.price;
  const savingsPercent = Math.round((savings / totalValue) * 100);

  return {
    totalValue,
    savings,
    savingsPercent,
  };
}
