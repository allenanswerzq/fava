import { equal, ok } from "node:assert/strict";
import { test } from "node:test";

import { mount, tick, unmount } from "svelte";

import PatchButton from "../src/editor/PatchButton.svelte";
import { setup_jsdom, user_events } from "./dom.ts";

test.beforeEach(setup_jsdom);

test("patch button enables for changes and writes a patch", async () => {
  let calls = 0;
  const target = document.querySelector("article");
  ok(target);
  const component = mount(PatchButton, {
    target,
    props: {
      changed: true,
      patching: false,
      onpatch: async () => {
        await Promise.resolve();
        calls += 1;
      },
    },
  });
  await tick();

  const button = target.querySelector("button");
  ok(button);
  equal(button.textContent.trim(), "Patch");
  equal(button.disabled, false);

  user_events.click(button);
  await tick();
  equal(calls, 1);

  await unmount(component);
});

test("patch button is disabled without changes", async () => {
  const target = document.querySelector("article");
  ok(target);
  const component = mount(PatchButton, {
    target,
    props: {
      changed: false,
      patching: false,
      onpatch: async () => {
        await Promise.resolve();
      },
    },
  });
  await tick();

  const button = target.querySelector("button");
  ok(button);
  equal(button.disabled, true);

  await unmount(component);
});

test("patch button shows its busy state", async () => {
  const target = document.querySelector("article");
  ok(target);
  const component = mount(PatchButton, {
    target,
    props: {
      changed: true,
      patching: true,
      onpatch: async () => {
        await Promise.resolve();
      },
    },
  });
  await tick();

  const button = target.querySelector("button");
  ok(button);
  equal(button.textContent.trim(), "Patching…");
  equal(button.disabled, true);

  await unmount(component);
});
