type PaginationControlsProps = {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
};

export function PaginationControls({ page, pageSize, total, onPageChange }: PaginationControlsProps) {
  const lastPage = Math.max(1, Math.ceil(total / pageSize));
  const start = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);
  const buttonClass = "rounded-md border border-border bg-white px-2.5 py-1.5 text-xs font-medium disabled:cursor-not-allowed disabled:opacity-40";

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 py-3 text-xs text-muted-foreground">
      <span>第 {start}–{end} 条，共 {total} 条</span>
      <div className="flex items-center gap-1">
        <button type="button" className={buttonClass} disabled={page <= 1} onClick={() => onPageChange(1)}>首页</button>
        <button type="button" className={buttonClass} disabled={page <= 1} onClick={() => onPageChange(page - 1)}>上一页</button>
        <span className="px-2">第 {page}/{lastPage} 页</span>
        <button type="button" className={buttonClass} disabled={page >= lastPage} onClick={() => onPageChange(page + 1)}>下一页</button>
        <button type="button" className={buttonClass} disabled={page >= lastPage} onClick={() => onPageChange(lastPage)}>末页</button>
      </div>
    </div>
  );
}
