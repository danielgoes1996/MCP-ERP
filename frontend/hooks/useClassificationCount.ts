/**
 * Hook to get pending classification count
 *
 * Fetches the number of pending classifications for the current company
 */

import { useEffect, useState } from 'react';
import { useAuthStore } from '@/stores/auth/useAuthStore';
import { getPendingClassifications } from '@/services/classificationService';

export function useClassificationCount() {
  const { tenant } = useAuthStore();
  const [count, setCount] = useState<number>(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchCount() {
      if (!tenant?.company_id) {
        setCount(0);
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        const data = await getPendingClassifications(tenant.company_id, 1, 0);
        setCount(data.total);
      } catch (error) {
        console.error('Error fetching classification count:', error);
        setCount(0);
      } finally {
        setLoading(false);
      }
    }

    fetchCount();

    // Refresh count every 30 seconds
    const interval = setInterval(fetchCount, 30000);

    return () => clearInterval(interval);
  }, [tenant?.company_id]);

  return { count, loading };
}
