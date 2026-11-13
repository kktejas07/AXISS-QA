export function LoadingSpinner() {
  return (
    <div role="status" aria-label="Loading" className="flex items-center justify-center py-12">
      <div className="h-8 w-8 animate-spin rounded-full border-4 border-line border-t-brand-600 motion-reduce:animate-none" />
    </div>
  );
}
