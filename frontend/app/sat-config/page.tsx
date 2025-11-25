/**
 * SAT Auto-Sync Configuration Page
 *
 * Allows users to configure automatic SAT invoice downloads
 */

'use client';

import { useState, useEffect } from 'react';
import { useAuthStore } from '@/stores/auth/useAuthStore';
import { useRouter } from 'next/navigation';
import {
  getSATSyncConfig,
  saveSATSyncConfig,
  triggerManualSync,
  getSyncHistory,
  type SATSyncConfig,
  type SATSyncConfigCreate,
} from '@/services/satSyncService';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';

export default function SATConfigPage() {
  const router = useRouter();
  const { user, tenant, isAuthenticated } = useAuthStore();

  // State
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [syncingManually, setSyncingManually] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [config, setConfig] = useState<SATSyncConfig | null>(null);

  // Form state
  const [formData, setFormData] = useState<SATSyncConfigCreate>({
    company_id: 0,
    enabled: false,
    frequency: 'weekly',
    day_of_week: 0,
    time: '02:00',
    lookback_days: 10,
    auto_classify: true,
    notify_email: true,
    notify_threshold: 5,
  });

  // Redirect if not authenticated
  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/login');
    }
  }, [isAuthenticated, router]);

  // Load configuration
  useEffect(() => {
    async function loadConfig() {
      const companyId = tenant?.company_id;

      // Validate company_id exists and is a valid number
      if (!companyId || isNaN(Number(companyId))) {
        console.log('No valid company_id found. Tenant:', tenant);
        setError('No se encontró ID de empresa. Por favor, vuelve a iniciar sesión.');
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        setError(null);

        const data = await getSATSyncConfig(Number(companyId));
        setConfig(data);

        // Populate form
        setFormData({
          company_id: data.company_id,
          enabled: data.enabled,
          frequency: data.frequency,
          day_of_week: data.day_of_week,
          time: data.time,
          lookback_days: data.lookback_days,
          auto_classify: data.auto_classify,
          notify_email: data.notify_email,
          notify_threshold: data.notify_threshold,
        });
      } catch (err: any) {
        // If config not found, create default
        if (err.message.includes('not found')) {
          setFormData((prev) => ({
            ...prev,
            company_id: Number(companyId),
          }));
        } else {
          console.error('Error loading SAT config:', err);
          setError('Error al cargar configuración');
        }
      } finally {
        setLoading(false);
      }
    }

    loadConfig();
  }, [tenant?.company_id]);

  // Handle form submit
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    try {
      setSaving(true);
      setError(null);
      setSuccessMessage(null);

      const savedConfig = await saveSATSyncConfig(formData);
      setConfig(savedConfig);
      setSuccessMessage('Configuración guardada exitosamente');

      // Clear success message after 3 seconds
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err) {
      console.error('Error saving config:', err);
      setError('Error al guardar configuración');
    } finally {
      setSaving(false);
    }
  };

  // Handle manual sync
  const handleManualSync = async () => {
    if (!tenant?.company_id) return;

    try {
      setSyncingManually(true);
      setError(null);
      setSuccessMessage(null);

      await triggerManualSync(Number(tenant.company_id));
      setSuccessMessage('Sincronización manual iniciada. Las facturas aparecerán en unos minutos.');

      // Clear success message after 5 seconds
      setTimeout(() => setSuccessMessage(null), 5000);
    } catch (err) {
      console.error('Error triggering manual sync:', err);
      setError('Error al iniciar sincronización manual');
    } finally {
      setSyncingManually(false);
    }
  };

  if (!isAuthenticated) {
    return null;
  }

  const dayNames = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'];

  return (
    <div className="min-h-screen bg-neutral-50">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-neutral-900 mb-2">
            Configuración de Sincronización SAT
          </h1>
          <p className="text-neutral-600">
            Configura la descarga automática de facturas desde el portal del SAT
          </p>
        </div>

        {/* Success Message */}
        {successMessage && (
          <div className="mb-6 p-4 bg-success-50 border-l-4 border-success-600 rounded">
            <p className="text-success-900 font-semibold">{successMessage}</p>
          </div>
        )}

        {/* Error Message */}
        {error && (
          <div className="mb-6 p-4 bg-error-50 border-l-4 border-error-600 rounded">
            <p className="text-error-900 font-semibold">{error}</p>
          </div>
        )}

        {/* Loading State */}
        {loading && (
          <Card className="p-6 animate-pulse">
            <div className="h-6 bg-neutral-300 rounded w-1/3 mb-4"></div>
            <div className="h-4 bg-neutral-200 rounded w-2/3 mb-2"></div>
            <div className="h-4 bg-neutral-200 rounded w-1/2"></div>
          </Card>
        )}

        {/* Configuration Form */}
        {!loading && (
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Enable/Disable */}
            <Card className="p-6">
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <h3 className="text-lg font-semibold text-neutral-900 mb-1">
                    Sincronización Automática
                  </h3>
                  <p className="text-sm text-neutral-600">
                    Activa la descarga automática de facturas del SAT
                  </p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.enabled}
                    onChange={(e) => setFormData({ ...formData, enabled: e.target.checked })}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-neutral-300 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-neutral-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-600"></div>
                </label>
              </div>
            </Card>

            {/* Frequency Settings */}
            <Card className="p-6">
              <h3 className="text-lg font-semibold text-neutral-900 mb-4">
                Frecuencia de Sincronización
              </h3>

              <div className="space-y-4">
                {/* Frequency Select */}
                <div>
                  <label className="block text-sm font-medium text-neutral-700 mb-2">
                    Frecuencia
                  </label>
                  <select
                    value={formData.frequency}
                    onChange={(e) =>
                      setFormData({ ...formData, frequency: e.target.value as any })
                    }
                    className="w-full px-4 py-2 border border-neutral-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                    disabled={!formData.enabled}
                  >
                    <option value="daily">Diario</option>
                    <option value="weekly">Semanal</option>
                    <option value="biweekly">Quincenal</option>
                    <option value="monthly">Mensual (día 1)</option>
                  </select>
                </div>

                {/* Day of Week (only for weekly/biweekly) */}
                {(formData.frequency === 'weekly' || formData.frequency === 'biweekly') && (
                  <div>
                    <label className="block text-sm font-medium text-neutral-700 mb-2">
                      Día de la semana
                    </label>
                    <select
                      value={formData.day_of_week ?? 0}
                      onChange={(e) =>
                        setFormData({ ...formData, day_of_week: parseInt(e.target.value) })
                      }
                      className="w-full px-4 py-2 border border-neutral-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                      disabled={!formData.enabled}
                    >
                      {dayNames.map((day, index) => (
                        <option key={index} value={index}>
                          {day}
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                {/* Time */}
                <div>
                  <label className="block text-sm font-medium text-neutral-700 mb-2">
                    Hora del día
                  </label>
                  <input
                    type="time"
                    value={formData.time}
                    onChange={(e) => setFormData({ ...formData, time: e.target.value })}
                    className="w-full px-4 py-2 border border-neutral-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                    disabled={!formData.enabled}
                  />
                  <p className="mt-1 text-xs text-neutral-500">
                    Recomendado: Horario nocturno para evitar carga en horas laborales
                  </p>
                </div>

                {/* Lookback Days */}
                <div>
                  <label className="block text-sm font-medium text-neutral-700 mb-2">
                    Días hacia atrás
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="30"
                    value={formData.lookback_days}
                    onChange={(e) =>
                      setFormData({ ...formData, lookback_days: parseInt(e.target.value) })
                    }
                    className="w-full px-4 py-2 border border-neutral-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                    disabled={!formData.enabled}
                  />
                  <p className="mt-1 text-xs text-neutral-500">
                    Ventana de descarga (incluye facturas timbradas tarde)
                  </p>
                </div>
              </div>
            </Card>

            {/* Advanced Options */}
            <Card className="p-6">
              <h3 className="text-lg font-semibold text-neutral-900 mb-4">
                Opciones Avanzadas
              </h3>

              <div className="space-y-4">
                {/* Auto Classify */}
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <h4 className="text-sm font-medium text-neutral-900">
                      Clasificación Automática
                    </h4>
                    <p className="text-xs text-neutral-600">
                      Clasificar facturas automáticamente con IA
                    </p>
                  </div>
                  <input
                    type="checkbox"
                    checked={formData.auto_classify}
                    onChange={(e) => setFormData({ ...formData, auto_classify: e.target.checked })}
                    disabled={!formData.enabled}
                    className="w-4 h-4 text-primary-600 border-neutral-300 rounded focus:ring-primary-500"
                  />
                </div>

                {/* Notify Email */}
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <h4 className="text-sm font-medium text-neutral-900">
                      Notificaciones por Email
                    </h4>
                    <p className="text-xs text-neutral-600">
                      Recibir email cuando hay facturas nuevas
                    </p>
                  </div>
                  <input
                    type="checkbox"
                    checked={formData.notify_email}
                    onChange={(e) => setFormData({ ...formData, notify_email: e.target.checked })}
                    disabled={!formData.enabled}
                    className="w-4 h-4 text-primary-600 border-neutral-300 rounded focus:ring-primary-500"
                  />
                </div>

                {/* Notify Threshold */}
                {formData.notify_email && (
                  <div>
                    <label className="block text-sm font-medium text-neutral-700 mb-2">
                      Umbral de notificación
                    </label>
                    <input
                      type="number"
                      min="1"
                      max="100"
                      value={formData.notify_threshold}
                      onChange={(e) =>
                        setFormData({ ...formData, notify_threshold: parseInt(e.target.value) })
                      }
                      className="w-full px-4 py-2 border border-neutral-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                      disabled={!formData.enabled}
                    />
                    <p className="mt-1 text-xs text-neutral-500">
                      Notificar solo si hay al menos N facturas nuevas
                    </p>
                  </div>
                )}
              </div>
            </Card>

            {/* Last Sync Info */}
            {config && config.last_sync_at && (
              <Card className="p-6 bg-neutral-50">
                <h3 className="text-lg font-semibold text-neutral-900 mb-4">
                  Última Sincronización
                </h3>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-neutral-600">Fecha:</span>
                    <span className="font-medium text-neutral-900">
                      {new Date(config.last_sync_at).toLocaleString('es-MX')}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-neutral-600">Estado:</span>
                    <span
                      className={`font-medium ${
                        config.last_sync_status === 'success'
                          ? 'text-success-600'
                          : 'text-error-600'
                      }`}
                    >
                      {config.last_sync_status === 'success' ? 'Exitosa' : 'Error'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-neutral-600">Facturas descargadas:</span>
                    <span className="font-medium text-neutral-900">{config.last_sync_count}</span>
                  </div>
                  {config.last_sync_error && (
                    <div className="mt-3 p-3 bg-error-50 rounded">
                      <p className="text-xs text-error-800">{config.last_sync_error}</p>
                    </div>
                  )}
                </div>
              </Card>
            )}

            {/* Action Buttons */}
            <div className="flex gap-4">
              <Button type="submit" disabled={saving} className="flex-1 bg-primary-600 hover:bg-primary-700 text-white">
                {saving ? 'Guardando...' : 'Guardar Configuración'}
              </Button>

              <Button
                type="button"
                onClick={handleManualSync}
                disabled={syncingManually || !tenant?.company_id}
                variant="outline"
                className="flex-1 border-primary-600 text-primary-700 hover:bg-primary-50"
              >
                {syncingManually ? 'Sincronizando...' : 'Sincronizar Ahora'}
              </Button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
