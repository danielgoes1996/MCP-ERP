/**
 * FixedAssetDepreciationInfo Component
 *
 * Displays depreciation information for fixed assets detected in invoices.
 * Shows fiscal (LISR) and accounting (NIF) rates with legal basis.
 *
 * Author: System
 * Date: 2025-11-28
 */

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Building2,
  FileText,
  ExternalLink,
  Plus,
  TrendingDown,
  Calendar,
  Scale,
  AlertCircle
} from 'lucide-react';

interface LegalBasis {
  law: string;
  article: string;
  section: string;
  article_text: string;
  effective_date: string;
  dof_url: string;
}

interface FixedAssetInfo {
  is_fixed_asset: boolean;
  asset_type: string;

  // Fiscal rates (LISR - for tax returns)
  depreciation_rate_fiscal_annual: number;
  depreciation_years_fiscal: number;
  depreciation_months_fiscal: number;

  // Accounting rates (NIF - for financial statements)
  depreciation_rate_accounting_annual: number;
  depreciation_years_accounting: number;
  depreciation_months_accounting: number;

  // Legal backing
  legal_basis: LegalBasis;

  // Context
  applies_to: string[];
  reasoning: string;
  confidence: number;

  // Deferred tax flag
  has_deferred_tax: boolean;
}

interface Props {
  data: FixedAssetInfo;
  onCreateAsset?: () => void;
}

const ASSET_TYPE_LABELS: Record<string, string> = {
  equipo_computo: 'Equipo de Cómputo',
  mobiliario: 'Mobiliario y Equipo de Oficina',
  vehiculos: 'Vehículos',
  maquinaria: 'Maquinaria Industrial',
  edificios: 'Edificios',
  terrenos: 'Terrenos',
  equipo_comunicacion: 'Equipo de Comunicación',
  activos_intangibles: 'Activos Intangibles',
  activos_biologicos: 'Activos Biológicos',
  herramental: 'Herramental',
  equipo_computo: 'Equipo de Cómputo'
};

export function FixedAssetDepreciationInfo({ data, onCreateAsset }: Props) {
  if (!data || !data.is_fixed_asset) {
    return null;
  }

  const assetTypeLabel = ASSET_TYPE_LABELS[data.asset_type] || data.asset_type;

  return (
    <Card className="mt-4 border-blue-200 bg-blue-50/50">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-blue-900">
          <Building2 className="h-5 w-5 text-blue-600" />
          Activo Fijo Detectado
          <Badge variant="outline" className="ml-auto bg-blue-100 text-blue-700 border-blue-300">
            {assetTypeLabel}
          </Badge>
        </CardTitle>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Alert for deferred tax */}
        {data.has_deferred_tax && (
          <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3">
            <AlertCircle className="h-5 w-5 text-amber-600 mt-0.5 flex-shrink-0" />
            <div className="flex-1">
              <p className="text-sm font-medium text-amber-900">
                Diferencia Fiscal-Contable (ISR Diferido)
              </p>
              <p className="mt-1 text-xs text-amber-700">
                Las tasas de depreciación fiscal y contable difieren, lo que genera impuestos diferidos.
              </p>
            </div>
          </div>
        )}

        {/* Depreciation rates */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Fiscal depreciation */}
          <div className="rounded-lg bg-white border border-blue-200 p-4 shadow-sm">
            <div className="flex items-center gap-2 mb-3">
              <Scale className="h-4 w-4 text-blue-600" />
              <h4 className="text-sm font-semibold text-gray-700">
                Depreciación Fiscal (SAT)
              </h4>
            </div>

            <div className="space-y-2">
              <div>
                <p className="text-3xl font-bold text-blue-600">
                  {data.depreciation_rate_fiscal_annual}%
                </p>
                <p className="text-xs text-gray-500">Tasa anual</p>
              </div>

              <div className="flex items-center gap-4 text-sm">
                <div>
                  <p className="font-medium text-gray-700">
                    {data.depreciation_years_fiscal} años
                  </p>
                  <p className="text-xs text-gray-500">Vida útil fiscal</p>
                </div>
                <div>
                  <p className="font-medium text-gray-700">
                    {data.depreciation_months_fiscal} meses
                  </p>
                  <p className="text-xs text-gray-500">Meses totales</p>
                </div>
              </div>
            </div>
          </div>

          {/* Accounting depreciation */}
          <div className="rounded-lg bg-white border border-green-200 p-4 shadow-sm">
            <div className="flex items-center gap-2 mb-3">
              <TrendingDown className="h-4 w-4 text-green-600" />
              <h4 className="text-sm font-semibold text-gray-700">
                Depreciación Contable (NIF)
              </h4>
            </div>

            <div className="space-y-2">
              <div>
                <p className="text-3xl font-bold text-green-600">
                  {data.depreciation_rate_accounting_annual}%
                </p>
                <p className="text-xs text-gray-500">Tasa anual</p>
              </div>

              <div className="flex items-center gap-4 text-sm">
                <div>
                  <p className="font-medium text-gray-700">
                    {data.depreciation_years_accounting} años
                  </p>
                  <p className="text-xs text-gray-500">Vida útil contable</p>
                </div>
                <div>
                  <p className="font-medium text-gray-700">
                    {data.depreciation_months_accounting} meses
                  </p>
                  <p className="text-xs text-gray-500">Meses totales</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Legal basis */}
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <div className="flex items-start gap-2">
            <FileText className="h-5 w-5 text-gray-400 mt-0.5 flex-shrink-0" />
            <div className="flex-1">
              <h4 className="font-semibold text-gray-900 mb-1">
                Fundamento Legal
              </h4>
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <Badge variant="secondary" className="font-mono text-xs">
                    {data.legal_basis.law}
                  </Badge>
                  <span className="text-sm text-gray-600">
                    Artículo {data.legal_basis.article} {data.legal_basis.section}
                  </span>
                </div>

                <p className="text-sm text-gray-700 italic border-l-2 border-gray-300 pl-3">
                  "{data.legal_basis.article_text}"
                </p>

                <div className="flex items-center gap-2 text-xs text-gray-500">
                  <Calendar className="h-3 w-3" />
                  <span>Vigente desde: {new Date(data.legal_basis.effective_date).toLocaleDateString('es-MX')}</span>
                </div>

                <a
                  href={data.legal_basis.dof_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center text-sm text-blue-600 hover:underline mt-2"
                >
                  Ver texto completo en DOF
                  <ExternalLink className="ml-1 h-3 w-3" />
                </a>
              </div>
            </div>
          </div>
        </div>

        {/* Applies to */}
        {data.applies_to && data.applies_to.length > 0 && (
          <div className="rounded-lg bg-gray-50 p-3">
            <h5 className="text-xs font-semibold text-gray-700 mb-2">
              Aplica a:
            </h5>
            <div className="flex flex-wrap gap-1">
              {data.applies_to.map((item, i) => (
                <Badge key={i} variant="secondary" className="text-xs">
                  {item}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {/* Reasoning */}
        <div className="rounded-lg bg-gray-50 p-3">
          <p className="text-sm text-gray-700">
            <strong>Razonamiento:</strong> {data.reasoning}
          </p>

          {/* Confidence bar */}
          <div className="mt-3 flex items-center gap-2">
            <div className="h-2 flex-1 rounded-full bg-gray-200">
              <div
                className={`h-2 rounded-full transition-all ${
                  data.confidence >= 0.8
                    ? 'bg-green-600'
                    : data.confidence >= 0.6
                    ? 'bg-yellow-600'
                    : 'bg-red-600'
                }`}
                style={{ width: `${data.confidence * 100}%` }}
              />
            </div>
            <span className="text-sm font-medium text-gray-600 min-w-[4rem] text-right">
              {(data.confidence * 100).toFixed(0)}% confianza
            </span>
          </div>
        </div>

        {/* Action button */}
        {onCreateAsset && (
          <Button
            onClick={onCreateAsset}
            className="w-full bg-blue-600 hover:bg-blue-700"
            size="lg"
          >
            <Plus className="mr-2 h-4 w-4" />
            Registrar como Activo Fijo
          </Button>
        )}
      </CardContent>
    </Card>
  );
}

export default FixedAssetDepreciationInfo;
