import { ReactNode } from "react";

interface UploadCardProps {
  title: string;
  description: string;
  constraintsText: string;
  children: ReactNode;
}

export function UploadCard({ title, description, constraintsText, children }: UploadCardProps): React.JSX.Element {
  return (
    <section className="card" aria-label={title}>
      <h2>{title}</h2>
      <p className="cardDescription">{description}</p>
      <p className="constraintText">Constraints: {constraintsText}</p>
      <div className="cardBody">{children}</div>
    </section>
  );
}
