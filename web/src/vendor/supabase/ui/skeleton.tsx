// Vendored from supabase/supabase (Apache-2.0), packages/ui, commit 6ac0316. See web/NOTICE.
import { cn } from '@/lib/utils'

function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('animate-pulse rounded-md bg-muted', className)} {...props} />
}

export { Skeleton }
