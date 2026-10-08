import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default: "border-transparent bg-primary text-primary-foreground hover:bg-primary/80",
        secondary: "border-transparent bg-slate-800 text-slate-300 hover:bg-slate-700",
        destructive: "border-transparent bg-rose-600/90 text-white shadow-sm",
        outline: "text-slate-300 border-slate-700",
        success: "border-transparent bg-emerald-600/90 text-white shadow-sm",
        warning: "border-transparent bg-amber-500/90 text-slate-950 font-bold shadow-sm",
        emergency: "border-rose-500 bg-rose-600 text-white animate-pulse shadow-md shadow-rose-900/50",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
