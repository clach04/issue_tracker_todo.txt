Deferred from web UI markdown rendering plan (docs/plans/webui-markdown-rendering.md, hash:e072da96, ADR-0008). Two parts: (1) code-fence highlighting in the client-side markdown-it output (e.g. <pre><code class="language-bash">), small hand-rolled highlighter for bash/python; (2) todo.txt/done.txt highlighting on the / list page (priority tokens, dates, project/context tags). Both client-side, consistent with the markdown-it rendering direction. No server-side changes needed; may be split into two issues later.

EXamples:

```bash
echo $my_var
echo ${my_var} 12 "hello"
```

```python
def something():
    return 1, "hello", 99+8
```

```c
void something()
{
    int x=1+33;
    char *c="hello";

    printf("hello");
}
```

