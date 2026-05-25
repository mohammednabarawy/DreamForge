import { useEffect, useState } from "react";
import { ImageIcon } from "lucide-react";
import { readImagePreviewQueued } from "../lib/preview-queue";

type Props = {
  path?: string;
  className?: string;
};

export function Thumb({ path, className = "h-10 w-10" }: Props) {
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!path) {
      setUrl(null);
      return;
    }
    let cancelled = false;
    void readImagePreviewQueued(path)
      .then((r) => {
        if (!cancelled) setUrl(r.data_url);
      })
      .catch(() => {
        if (!cancelled) setUrl(null);
      });
    return () => {
      cancelled = true;
    };
  }, [path]);

  if (!url) {
    return (
      <div
        className={`flex shrink-0 items-center justify-center rounded-md border border-dfui-border/50 bg-dfui-bg/80 ${className}`}
      >
        <ImageIcon size={14} className="text-dfui-muted" />
      </div>
    );
  }

  return (
    <img
      src={url}
      alt=""
      className={`shrink-0 rounded-md border border-dfui-border/50 object-cover ${className}`}
    />
  );
}
