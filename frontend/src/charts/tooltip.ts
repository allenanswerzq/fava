import type { Attachment } from "svelte/attachments";

/** A tooltip, wrapping a `<div>` positioned within its chart container. */
export class Tooltip {
  private div: HTMLDivElement;
  private container: HTMLElement | null = null;

  constructor() {
    this.div = document.createElement("div");
    this.div.className = "tooltip top";
  }

  init(node: HTMLElement): void {
    this.container = node;
    node.appendChild(this.div);
  }

  /** Set the tooltip content. */
  content(nodes: (Node | string)[]): void {
    this.div.replaceChildren(...nodes);
  }

  /** Position the tooltip. */
  position(left: number, top: number): void {
    this.div.style.opacity = "1";
    this.div.style.left = `${Math.round(left).toString()}px`;
    this.div.style.top = `${Math.round(top).toString()}px`;
  }

  /** Hide the tooltip. */
  hide(): void {
    this.div.style.opacity = "0";
  }

  /**
   * Svelte attachment to have the given element act on mouse to show a tooltip.
   *
   * The tooltip will be positioned at the cursor and is given a tooltip getter
   * per element.
   */
  following(getter: () => (Node | string)[]): Attachment<SVGElement> {
    return (node) => {
      const mouseenter = () => {
        this.content(getter());
      };
      const mousemove = (event: MouseEvent) => {
        const bounds = this.container?.getBoundingClientRect();
        if (bounds) {
          this.position(
            event.clientX - bounds.left,
            event.clientY - bounds.top,
          );
        }
      };
      const hide = this.hide.bind(this);

      node.addEventListener("mouseenter", mouseenter);
      node.addEventListener("mousemove", mousemove);
      node.addEventListener("mouseleave", hide);

      return () => {
        node.removeEventListener("mouseenter", mouseenter);
        node.removeEventListener("mousemove", mousemove);
        node.removeEventListener("mouseleave", hide);
      };
    };
  }
}

/** Some small utilities to create tooltip contents. */
export const domHelpers = {
  /** Create a <br> element. */
  br: () => document.createElement("br"),
  /** Create a <em> element with the given content. */
  em: (content) => {
    const em = document.createElement("em");
    em.textContent = content;
    return em;
  },
} satisfies Record<string, (x: string) => HTMLElement>;

export type TooltipContent = (HTMLElement | string)[];

/**
 * A function to find the closest node to the pointer.
 *
 * Returns the position of the node, the node itself, and a function to create
 * the content to show in the tooltip for it.
 */
export type TooltipFindNode = (
  x_pointer: number,
  y_pointer: number,
) =>
  | [x: number, y: number, node: unknown, content: () => TooltipContent]
  | undefined;
