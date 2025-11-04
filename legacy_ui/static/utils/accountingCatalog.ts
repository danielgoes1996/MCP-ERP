export interface AccountingCategory {
  slug: string;
  nombre: string;
  descripcion: string;
  sinonimos: string[];
}

export interface CategoryNormalization {
  slug: string;
  nombre: string;
  confianza: number;
  fuente: string;
  matched_by: string;
}

export async function fetchAccountingCatalog(): Promise<AccountingCategory[]> {
  const response = await fetch('/accounting-catalog');
  if (!response.ok) {
    throw new Error(`No se pudo cargar el catálogo contable (${response.status})`);
  }
  return response.json();
}

export async function normalizeAccountingCategory(value: string): Promise<CategoryNormalization> {
  const response = await fetch('/accounting-categories/normalize', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ raw_value: value })
  });

  if (!response.ok) {
    throw new Error(`No se pudo normalizar la categoría (${response.status})`);
  }

  return response.json();
}

