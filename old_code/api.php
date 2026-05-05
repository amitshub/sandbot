public function rag_pages()
{
    header("Content-Type: application/json");

    $sitemap_url = "https://sandlus.com/sitemap.xml";

    $xml = simplexml_load_file($sitemap_url);

    $pages = [];

    foreach ($xml->url as $url_obj) {

        $url = (string)$url_obj->loc;

        try {
            $html = file_get_contents($url);

            // Remove HTML tags
            $text = strip_tags($html);

            // Clean text
            $text = preg_replace('/\s+/', ' ', $text);

            if (strlen($text) > 100) {
                $pages[] = [
                    "url" => $url,
                    "content" => $text
                ];
            }

        } catch (Exception $e) {
            // skip failed pages
            continue;
        }
    }

    echo json_encode([
        "success" => true,
        "pages" => $pages
    ]);
}