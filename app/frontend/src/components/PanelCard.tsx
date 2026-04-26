import { ReactNode } from "react";

type PanelCardProps = {
  title: string;
  subtitle?: string;
  children: ReactNode;
};

export function PanelCard({ title, subtitle, children }: PanelCardProps) {
  return (
    <section className="panel">
      <header className="panelHeader">
        <h2>{title}</h2>
        {subtitle ? <p>{subtitle}</p> : null}
      </header>
      <div className="panelBody">{children}</div>
    </section>
  );
}
