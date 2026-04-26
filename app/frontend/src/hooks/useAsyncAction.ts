import { useCallback, useState } from "react";

type AsyncState<T> = {
  loading: boolean;
  data: T | null;
  error: string | null;
};

export function useAsyncAction<T>() {
  const [state, setState] = useState<AsyncState<T>>({
    loading: false,
    data: null,
    error: null,
  });

  const execute = useCallback(async (action: () => Promise<T>): Promise<T | null> => {
    setState({ loading: true, data: null, error: null });
    try {
      const data = await action();
      setState({ loading: false, data, error: null });
      return data;
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unexpected error";
      setState({ loading: false, data: null, error: message });
      return null;
    }
  }, []);

  const reset = useCallback(() => {
    setState({ loading: false, data: null, error: null });
  }, []);

  return {
    ...state,
    execute,
    reset,
  };
}
