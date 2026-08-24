import Image from "next/image";
import type { ReactNode } from "react";

type ReportPageHeroProps = {
  eyebrow: string;
  title: string;
  description?: string;
  imageSrc: string;
  imagePosition?: string;
  animated?: boolean;
  meta?: ReactNode;
  action?: ReactNode;
};

export function ReportPageHero({
  eyebrow,
  title,
  description,
  imageSrc,
  imagePosition = "50% 50%",
  animated = false,
  meta,
  action,
}: ReportPageHeroProps) {
  return (
    <section className="relative flex flex-col gap-5 overflow-hidden rounded-2xl border border-emerald-100/80 bg-emerald-50/60 p-6 lg:flex-row lg:items-end lg:justify-between">
      <Image
        src={imageSrc}
        alt=""
        aria-hidden="true"
        fill
        sizes="(min-width: 1280px) 1152px, 100vw"
        style={{ objectPosition: imagePosition }}
        className={`${animated ? "animate-ken-burns " : ""}pointer-events-none object-cover opacity-[0.23] brightness-95 saturate-125`}
      />
      <div className="relative min-w-0">
        <p className="text-sm font-semibold text-emerald-700">{eyebrow}</p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">{title}</h1>
        {meta ? (
          <div className="mt-3 flex flex-wrap items-center gap-2">{meta}</div>
        ) : null}
        {description ? (
          <p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">
            {description}
          </p>
        ) : null}
      </div>
      {action ? <div className="relative shrink-0">{action}</div> : null}
    </section>
  );
}
