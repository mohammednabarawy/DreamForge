import { useEffect, useRef, useState } from "react";
import { ImageIcon } from "lucide-react";
import { readImagePreviewQueued } from "../lib/preview-queue";

type Props = {
  path?: string;
  className?: string;
};

export function Thumb({ path, className = "h-10 w-10" }: Props) {
  const [url, setUrl] = useState<string | null>(null);
  const container = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        setVisible(true);
        observer.disconnect();
      }
    }, { rootMargin: "200px" });
    if (container.current) observer.observe(container.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    setUrl(null);
    if (!path || !visible) return;
    let cancelled = false;
    void readImagePreviewQueued(path, { quality: "thumbnail" })
      .then((r) => {
        if (!cancelled) setUrl(r.data_url);
      })
      .catch(() => {
        if (!cancelled) setUrl(null);
      });
    return () => {
      cancelled = true;
    };
  }, [path, visible]);

  return (
    <div ref={container}
      className={`flex shrink-0 items-center justify-center overflow-hidden rounded-md border border-dfui-border/50 bg-dfui-bg/80 ${className}`}>
      {url ? <img src={url} alt="" draggable={false} className="h-full w-full object-cover" />
        : <ImageIcon size={14} className="text-dfui-muted" />}
    </div>
  );
}
