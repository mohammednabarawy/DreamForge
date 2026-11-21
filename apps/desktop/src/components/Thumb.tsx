import { useEffect, useRef, useState } from "react";
import { ImageIcon, RotateCw } from "lucide-react";
import {
  getCachedThumbnailUrl,
  invalidateThumbnailCache,
  readImagePreviewQueued,
} from "../lib/preview-queue";

type Props = {
  path?: string;
  className?: string;
};

export function Thumb({ path, className = "h-10 w-10" }: Props) {
  const [url, setUrl] = useState<string | null>(() => getCachedThumbnailUrl(path));
  const [loading, setLoading] = useState<boolean>(() => Boolean(path && !getCachedThumbnailUrl(path)));
  const [failed, setFailed] = useState(false);
  const [retryToken, setRetryToken] = useState(0);
  const container = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState<boolean>(() =>
    Boolean(getCachedThumbnailUrl(path) || typeof IntersectionObserver === "undefined"),
  );

  useEffect(() => {
    if (visible) return;
    const node = container.current;
    if (!node || typeof IntersectionObserver === "undefined") {
      setVisible(true);
      return;
    }
    const rect = node.getBoundingClientRect();
    if (rect.height > 0 && rect.top < window.innerHeight + 240 && rect.bottom > -240) {
      setVisible(true);
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin: "240px" },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [visible, path]);

  useEffect(() => {
    if (!path) {
      setUrl(null);
      setLoading(false);
      setFailed(false);
      return;
    }
    if (retryToken === 0) {
      const cached = getCachedThumbnailUrl(path);
      if (cached) {
        setUrl(cached);
        setLoading(false);
        setFailed(false);
        return;
      }
    }
    if (!visible) return;

    let cancelled = false;
    setLoading(true);
    setFailed(false);
    void readImagePreviewQueued(path, {
      quality: "thumbnail",
      bypassCache: retryToken > 0,
    })
      .then((r) => {
        if (cancelled) return;
        if (r.data_url) {
          setUrl(r.data_url);
          setFailed(false);
        } else {
          setUrl(null);
          setFailed(true);
        }
      })
      .catch(() => {
        if (cancelled) return;
        setUrl(null);
        setFailed(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [path, visible, retryToken]);

  return (
    <div
      ref={container}
      className={`flex shrink-0 items-center justify-center overflow-hidden rounded-md border border-dfui-border/50 bg-dfui-bg/80 ${className}`}
    >
      {url ? (
        <img
          src={url}
          alt=""
          draggable={false}
          className="h-full w-full object-cover"
          onError={() => {
            if (path) invalidateThumbnailCache(path);
            setUrl(null);
            setFailed(true);
          }}
        />
      ) : failed ? (
        <span
          role="button"
          tabIndex={-1}
          title="Thumbnail failed to load — click to retry"
          onClick={(e) => {
            e.stopPropagation();
            if (path) invalidateThumbnailCache(path);
            setVisible(true);
            setRetryToken((t) => t + 1);
          }}
          className="flex h-full w-full items-center justify-center text-dfui-tertiary hover:text-dfui-fg"
        >
          <RotateCw size={12} />
        </span>
      ) : loading && path ? (
        <div className="h-full w-full animate-pulse bg-dfui-panel/70" />
      ) : (
        <ImageIcon size={14} className="text-dfui-muted" />
      )}
    </div>
  );
}
