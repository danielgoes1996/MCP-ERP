/**
 * Chedraui Store Locations - 16 tiendas donde está disponible Carreta Verde
 * Formato compatible con StoreLocator component
 */

export interface Store {
  id: number;
  name: string;
  type: string;
  address: string;
  city: string;
  state: string;
  zipCode: string;
  lat: number;
  lng: number;
  phone: string;
  hours: string;
  rating: number;
  products: string[];
  isOpen: boolean;
}

export const CHEDRAUI_LOCATIONS: Store[] = [
  // ========== CDMX (7 tiendas) ==========
  {
    id: 1,
    name: 'Chedraui Selecto Santa Fe',
    type: 'supermercado',
    address: 'Av. Vasco de Quiroga 3800, Santa Fe',
    city: 'CDMX',
    state: 'Ciudad de México',
    zipCode: '05348',
    lat: 19.3575,
    lng: -99.2615,
    phone: '55 5257 8600',
    hours: 'Lun-Dom 8:00-22:00',
    rating: 4.5,
    products: ['Miel de Flor de Aceitilla', 'Miel Multifloral'],
    isOpen: true
  },
  {
    id: 2,
    name: 'Chedraui Selecto Interlomas',
    type: 'supermercado',
    address: 'Vialidad de la Barranca 6, Interlomas',
    city: 'CDMX',
    state: 'Ciudad de México',
    zipCode: '52787',
    lat: 19.3888,
    lng: -99.2577,
    phone: '55 5290 8800',
    hours: 'Lun-Dom 8:00-22:00',
    rating: 4.6,
    products: ['Miel de Flor de Aceitilla', 'Miel Multifloral'],
    isOpen: true
  },
  {
    id: 3,
    name: 'Chedraui Bellavista',
    type: 'supermercado',
    address: 'Av. Insurgentes Sur 1605, Benito Juárez',
    city: 'CDMX',
    state: 'Ciudad de México',
    zipCode: '03100',
    lat: 19.3785,
    lng: -99.1725,
    phone: '55 5663 5200',
    hours: 'Lun-Dom 7:00-23:00',
    rating: 4.3,
    products: ['Miel de Flor de Aceitilla', 'Miel Multifloral'],
    isOpen: true
  },
  {
    id: 4,
    name: 'Chedraui Mundo E',
    type: 'supermercado',
    address: 'Calzada de Tlalpan 1341, Portales',
    city: 'CDMX',
    state: 'Ciudad de México',
    zipCode: '03300',
    lat: 19.3605,
    lng: -99.1555,
    phone: '55 5674 3300',
    hours: 'Lun-Dom 7:00-23:00',
    rating: 4.4,
    products: ['Miel de Flor de Aceitilla', 'Miel Multifloral'],
    isOpen: true
  },
  {
    id: 5,
    name: 'Chedraui Selecto Centro Sur',
    type: 'supermercado',
    address: 'Insurgentes Sur 1971, Guadalupe Inn',
    city: 'CDMX',
    state: 'Ciudad de México',
    zipCode: '01020',
    lat: 19.3535,
    lng: -99.1785,
    phone: '55 5661 9900',
    hours: 'Lun-Dom 8:00-22:00',
    rating: 4.5,
    products: ['Miel de Flor de Aceitilla', 'Miel Multifloral'],
    isOpen: true
  },
  {
    id: 6,
    name: 'Chedraui Coyoacán',
    type: 'supermercado',
    address: 'Av. Universidad 1705, Coyoacán',
    city: 'CDMX',
    state: 'Ciudad de México',
    zipCode: '04000',
    lat: 19.3425,
    lng: -99.1625,
    phone: '55 5658 4400',
    hours: 'Lun-Dom 7:00-23:00',
    rating: 4.2,
    products: ['Miel de Flor de Aceitilla', 'Miel Multifloral'],
    isOpen: true
  },
  {
    id: 7,
    name: 'Chedraui Churubusco',
    type: 'supermercado',
    address: 'Calz. de Tlalpan 1900, Country Club',
    city: 'CDMX',
    state: 'Ciudad de México',
    zipCode: '04220',
    lat: 19.3215,
    lng: -99.1545,
    phone: '55 5544 8800',
    hours: 'Lun-Dom 7:00-23:00',
    rating: 4.3,
    products: ['Miel de Flor de Aceitilla', 'Miel Multifloral'],
    isOpen: true
  },

  // ========== Querétaro (3 tiendas) ==========
  {
    id: 8,
    name: 'Chedraui Querétaro Norte',
    type: 'supermercado',
    address: 'Av. Prolongación Bernardo Quintana 4050',
    city: 'Querétaro',
    state: 'Querétaro',
    zipCode: '76090',
    lat: 20.6285,
    lng: -100.3895,
    phone: '442 245 6700',
    hours: 'Lun-Dom 7:00-23:00',
    rating: 4.4,
    products: ['Miel de Flor de Aceitilla', 'Miel Multifloral'],
    isOpen: true
  },
  {
    id: 9,
    name: 'Chedraui Selecto Antea',
    type: 'supermercado',
    address: 'Blvd. Antea 1001, Jurica',
    city: 'Querétaro',
    state: 'Querétaro',
    zipCode: '76100',
    lat: 20.6515,
    lng: -100.4355,
    phone: '442 688 0300',
    hours: 'Lun-Dom 8:00-22:00',
    rating: 4.7,
    products: ['Miel de Flor de Aceitilla', 'Miel Multifloral'],
    isOpen: true
  },
  {
    id: 10,
    name: 'Chedraui Querétaro Centro',
    type: 'supermercado',
    address: 'Av. 5 de Febrero 110, Centro',
    city: 'Querétaro',
    state: 'Querétaro',
    zipCode: '76000',
    lat: 20.5885,
    lng: -100.3915,
    phone: '442 212 3400',
    hours: 'Lun-Dom 7:00-23:00',
    rating: 4.2,
    products: ['Miel de Flor de Aceitilla', 'Miel Multifloral'],
    isOpen: true
  },

  // ========== Corregidora, Qro (2 tiendas) ==========
  {
    id: 11,
    name: 'Chedraui Corregidora',
    type: 'supermercado',
    address: 'Av. Pie de la Cuesta 2505, El Pueblito',
    city: 'Corregidora',
    state: 'Querétaro',
    zipCode: '76900',
    lat: 20.5325,
    lng: -100.4415,
    phone: '442 228 8900',
    hours: 'Lun-Dom 7:00-23:00',
    rating: 4.3,
    products: ['Miel de Flor de Aceitilla', 'Miel Multifloral'],
    isOpen: true
  },
  {
    id: 12,
    name: 'Chedraui El Refugio',
    type: 'supermercado',
    address: 'Carr. Querétaro-México Km 27, El Refugio',
    city: 'Corregidora',
    state: 'Querétaro',
    zipCode: '76904',
    lat: 20.5145,
    lng: -100.3885,
    phone: '442 229 1100',
    hours: 'Lun-Dom 7:00-23:00',
    rating: 4.4,
    products: ['Miel de Flor de Aceitilla', 'Miel Multifloral'],
    isOpen: true
  },

  // ========== Morelia (4 tiendas) ==========
  {
    id: 13,
    name: 'Chedraui Morelia Centro',
    type: 'supermercado',
    address: 'Av. Camelinas 3233, Sentimientos de la Nación',
    city: 'Morelia',
    state: 'Michoacán',
    zipCode: '58290',
    lat: 19.6885,
    lng: -101.1755,
    phone: '443 324 5600',
    hours: 'Lun-Dom 7:00-23:00',
    rating: 4.3,
    products: ['Miel de Flor de Aceitilla', 'Miel Multifloral'],
    isOpen: true
  },
  {
    id: 14,
    name: 'Chedraui Selecto Morelia',
    type: 'supermercado',
    address: 'Periférico Paseo de la República 2810',
    city: 'Morelia',
    state: 'Michoacán',
    zipCode: '58000',
    lat: 19.7025,
    lng: -101.1885,
    phone: '443 327 8800',
    hours: 'Lun-Dom 8:00-22:00',
    rating: 4.6,
    products: ['Miel de Flor de Aceitilla', 'Miel Multifloral'],
    isOpen: true
  },
  {
    id: 15,
    name: 'Chedraui Morelia Altozano',
    type: 'supermercado',
    address: 'Av. Montaña Monarca Norte 1000, Altozano',
    city: 'Morelia',
    state: 'Michoacán',
    zipCode: '58090',
    lat: 19.7455,
    lng: -101.2335,
    phone: '443 334 7700',
    hours: 'Lun-Dom 7:00-23:00',
    rating: 4.5,
    products: ['Miel de Flor de Aceitilla', 'Miel Multifloral'],
    isOpen: true
  },
  {
    id: 16,
    name: 'Chedraui Las Américas',
    type: 'supermercado',
    address: 'Av. Periodismo 2000, Las Américas',
    city: 'Morelia',
    state: 'Michoacán',
    zipCode: '58270',
    lat: 19.6745,
    lng: -101.1945,
    phone: '443 316 9900',
    hours: 'Lun-Dom 7:00-23:00',
    rating: 4.2,
    products: ['Miel de Flor de Aceitilla', 'Miel Multifloral'],
    isOpen: true
  }
];
