/**
 * Modern Line Items Table Component
 * Inline editing with drag-and-drop reordering
 * Auto-calculations and smart defaults
 */

'use client';

import { useState, useEffect } from 'react';
import { motion, Reorder } from 'framer-motion';
import {
  GripVertical,
  Plus,
  Trash2,
  Upload,
  AlertCircle,
  Calculator,
} from 'lucide-react';

export interface POLineItem {
  line_number: number;
  sku?: string;
  description: string;
  unit_of_measure: string;
  quantity: number;
  unit_price: number;
  line_total: number;
  clave_prod_serv?: string;
  notes?: string;
}

interface LineItemsTableProps {
  lines: POLineItem[];
  onChange: (lines: POLineItem[]) => void;
  errors?: Record<number, string>;
}

export function LineItemsTable({ lines, onChange, errors = {} }: LineItemsTableProps) {
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Auto-calculate line total when quantity or price changes
  const updateLine = (index: number, field: keyof POLineItem, value: any) => {
    const newLines = [...lines];
    newLines[index] = { ...newLines[index], [field]: value };

    // Auto-calculate total
    if (field === 'quantity' || field === 'unit_price') {
      const quantity = field === 'quantity' ? parseFloat(value) || 0 : newLines[index].quantity;
      const price = field === 'unit_price' ? parseFloat(value) || 0 : newLines[index].unit_price;
      newLines[index].line_total = quantity * price;
    }

    onChange(newLines);
  };

  const addLine = () => {
    const newLine: POLineItem = {
      line_number: lines.length + 1,
      description: '',
      unit_of_measure: 'PZA',
      quantity: 1,
      unit_price: 0,
      line_total: 0,
    };
    onChange([...lines, newLine]);
  };

  const removeLine = (index: number) => {
    const newLines = lines.filter((_, i) => i !== index);
    // Renumber lines
    newLines.forEach((line, i) => {
      line.line_number = i + 1;
    });
    onChange(newLines);
  };

  const handleReorder = (newOrder: POLineItem[]) => {
    // Renumber after reordering
    newOrder.forEach((line, i) => {
      line.line_number = i + 1;
    });
    onChange(newOrder);
  };

  const calculateTotal = () => {
    return lines.reduce((sum, line) => sum + (line.line_total || 0), 0);
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('es-MX', {
      style: 'currency',
      currency: 'MXN',
      minimumFractionDigits: 2,
    }).format(amount);
  };

  if (lines.length === 0) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="border-2 border-dashed border-gray-300 rounded-xl p-12 text-center"
      >
        <div className="max-w-sm mx-auto space-y-4">
          <div className="p-4 bg-gray-100 rounded-full w-16 h-16 mx-auto flex items-center justify-center">
            <Calculator className="w-8 h-8 text-gray-400" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              Sin líneas de productos
            </h3>
            <p className="text-sm text-gray-500 mb-6">
              Agrega productos o servicios individuales para un mejor seguimiento.
              Esto es opcional pero recomendado para órdenes detalladas.
            </p>
          </div>
          <button
            onClick={addLine}
            className="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-[#60b97b] to-[#4a9460] hover:from-[#4a9460] hover:to-[#60b97b] text-white rounded-xl font-semibold shadow-lg hover:shadow-xl transition-all"
          >
            <Plus className="w-5 h-5" />
            Agregar primera línea
          </button>
        </div>
      </motion.div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-bold text-gray-900">
            Líneas de productos ({lines.length})
          </h3>
          <p className="text-sm text-gray-500">
            Arrastra para reordenar • Click para editar
          </p>
        </div>
        <button
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="text-sm text-[#11446e] hover:text-[#60b97b] font-medium transition-colors"
        >
          {showAdvanced ? 'Ocultar' : 'Mostrar'} campos avanzados
        </button>
      </div>

      {/* Table Header */}
      <div className="grid grid-cols-12 gap-3 px-4 py-2 bg-gray-50 rounded-lg text-xs font-semibold text-gray-600">
        <div className="col-span-1">#</div>
        <div className="col-span-4">Descripción</div>
        <div className="col-span-2 text-center">Cantidad</div>
        <div className="col-span-2 text-center">Precio Unit.</div>
        <div className="col-span-2 text-right">Total</div>
        <div className="col-span-1"></div>
      </div>

      {/* Reorderable Lines */}
      <Reorder.Group
        axis="y"
        values={lines}
        onReorder={handleReorder}
        className="space-y-2"
      >
        {lines.map((line, index) => (
          <Reorder.Item key={`line-${index}`} value={line}>
            <motion.div
              layout
              className="group bg-white border-2 border-gray-200 hover:border-[#11446e]/30 rounded-xl p-4 transition-all hover:shadow-md"
            >
              {/* Main Row */}
              <div className="grid grid-cols-12 gap-3 items-center">
                {/* Drag Handle + Line Number */}
                <div className="col-span-1 flex items-center gap-2">
                  <GripVertical className="w-4 h-4 text-gray-400 cursor-grab active:cursor-grabbing opacity-0 group-hover:opacity-100 transition-opacity" />
                  <span className="text-sm font-semibold text-gray-500">
                    {line.line_number}
                  </span>
                </div>

                {/* Description */}
                <div className="col-span-4">
                  <input
                    type="text"
                    value={line.description}
                    onChange={(e) => updateLine(index, 'description', e.target.value)}
                    placeholder="Ej: Montacargas Cat 2000"
                    className="w-full px-3 py-2 border-0 bg-gray-50 rounded-lg text-sm focus:ring-2 focus:ring-[#11446e] focus:bg-white transition-all"
                  />
                  {errors[index] && (
                    <p className="mt-1 text-xs text-red-600 flex items-center gap-1">
                      <AlertCircle className="w-3 h-3" />
                      {errors[index]}
                    </p>
                  )}
                </div>

                {/* Quantity */}
                <div className="col-span-2">
                  <div className="flex items-center gap-2">
                    <input
                      type="number"
                      value={line.quantity}
                      onChange={(e) =>
                        updateLine(index, 'quantity', parseFloat(e.target.value) || 0)
                      }
                      min="0"
                      step="0.01"
                      className="w-20 px-3 py-2 border-0 bg-gray-50 rounded-lg text-sm text-center focus:ring-2 focus:ring-[#11446e] focus:bg-white transition-all"
                    />
                    <select
                      value={line.unit_of_measure}
                      onChange={(e) => updateLine(index, 'unit_of_measure', e.target.value)}
                      className="flex-1 px-2 py-2 border-0 bg-gray-50 rounded-lg text-xs focus:ring-2 focus:ring-[#11446e] focus:bg-white transition-all"
                    >
                      <option value="PZA">PZA</option>
                      <option value="KG">KG</option>
                      <option value="M">M</option>
                      <option value="HR">HR</option>
                      <option value="LT">LT</option>
                      <option value="SRV">SRV</option>
                    </select>
                  </div>
                </div>

                {/* Unit Price */}
                <div className="col-span-2">
                  <input
                    type="number"
                    value={line.unit_price}
                    onChange={(e) =>
                      updateLine(index, 'unit_price', parseFloat(e.target.value) || 0)
                    }
                    min="0"
                    step="0.01"
                    placeholder="0.00"
                    className="w-full px-3 py-2 border-0 bg-gray-50 rounded-lg text-sm text-center focus:ring-2 focus:ring-[#11446e] focus:bg-white transition-all"
                  />
                </div>

                {/* Line Total (auto-calculated) */}
                <div className="col-span-2 text-right">
                  <span className="text-sm font-bold text-gray-900">
                    {formatCurrency(line.line_total)}
                  </span>
                </div>

                {/* Delete Button */}
                <div className="col-span-1 flex justify-end">
                  <button
                    onClick={() => removeLine(index)}
                    className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors opacity-0 group-hover:opacity-100"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* Advanced Fields (Collapsible) */}
              {showAdvanced && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="mt-3 pt-3 border-t border-gray-200 grid grid-cols-3 gap-3"
                >
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">
                      SKU/Código
                    </label>
                    <input
                      type="text"
                      value={line.sku || ''}
                      onChange={(e) => updateLine(index, 'sku', e.target.value)}
                      placeholder="CAT-MC-2000"
                      className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-[#11446e] focus:border-transparent"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">
                      Clave SAT (Opcional)
                    </label>
                    <input
                      type="text"
                      value={line.clave_prod_serv || ''}
                      onChange={(e) => updateLine(index, 'clave_prod_serv', e.target.value)}
                      placeholder="43211500"
                      maxLength={20}
                      className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-[#11446e] focus:border-transparent"
                    />
                  </div>

                  <div className="col-span-3">
                    <label className="block text-xs font-medium text-gray-600 mb-1">
                      Notas
                    </label>
                    <input
                      type="text"
                      value={line.notes || ''}
                      onChange={(e) => updateLine(index, 'notes', e.target.value)}
                      placeholder="Información adicional sobre esta línea..."
                      className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-[#11446e] focus:border-transparent"
                    />
                  </div>
                </motion.div>
              )}
            </motion.div>
          </Reorder.Item>
        ))}
      </Reorder.Group>

      {/* Add Line Button */}
      <motion.button
        whileHover={{ scale: 1.01 }}
        whileTap={{ scale: 0.99 }}
        onClick={addLine}
        className="w-full flex items-center justify-center gap-2 px-4 py-3 border-2 border-dashed border-gray-300 hover:border-[#11446e] rounded-xl text-gray-600 hover:text-[#11446e] font-medium transition-colors group"
      >
        <Plus className="w-5 h-5 group-hover:rotate-90 transition-transform" />
        Agregar otra línea
      </motion.button>

      {/* Total Summary */}
      <div className="flex items-center justify-between p-4 bg-gradient-to-br from-gray-50 to-white border-2 border-gray-200 rounded-xl">
        <div className="flex items-center gap-2">
          <Calculator className="w-5 h-5 text-gray-500" />
          <span className="font-semibold text-gray-700">Total de líneas:</span>
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold text-gray-900">
            {formatCurrency(calculateTotal())}
          </div>
          <div className="text-xs text-gray-500">
            {lines.length} {lines.length === 1 ? 'línea' : 'líneas'}
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="flex gap-3 text-sm">
        <button className="flex items-center gap-2 px-4 py-2 text-gray-600 hover:text-[#11446e] hover:bg-gray-50 rounded-lg transition-colors">
          <Upload className="w-4 h-4" />
          Importar desde Excel
        </button>
        <button className="flex items-center gap-2 px-4 py-2 text-gray-600 hover:text-[#11446e] hover:bg-gray-50 rounded-lg transition-colors">
          <Upload className="w-4 h-4" />
          Pegar desde cotización
        </button>
      </div>
    </div>
  );
}
