/* Regression checks against the actual shared FFmpeg library. */
#include <assert.h>
#include <string.h>
#include <sys/resource.h>

#include <libavutil/encryption_info.h>
#include <libavutil/hdr_dynamic_metadata.h>
#include <libavutil/mem.h>
#include <libavutil/rational.h>

int main(int argc, char **argv)
{
    assert(argc == 2);
    if (strcmp(argv[1], "encryption") == 0) {
        AVEncryptionInitInfo *head = NULL;
        struct rlimit stack = {128 * 1024, 128 * 1024};
        assert(setrlimit(RLIMIT_STACK, &stack) == 0);
        for (int i = 0; i < 100000; i++) {
            AVEncryptionInitInfo *node = av_encryption_init_info_alloc(0, 0, 0, 0);
            assert(node);
            node->next = head;
            head = node;
        }
        av_encryption_init_info_free(head);
    } else {
        assert(strcmp(argv[1], "hdr") == 0);
        AVDynamicHDRPlus *hdr = av_dynamic_hdr_plus_alloc(NULL);
        AVDynamicHDRPlus *parsed = av_dynamic_hdr_plus_alloc(NULL);
        assert(hdr && parsed);
        hdr->num_windows = 1;
        hdr->targeted_system_display_maximum_luminance.den = 1;
        for (int i = 0; i < 3; i++)
            hdr->params[0].maxscl[i].den = 1;
        hdr->params[0].average_maxrgb.den = 1;
        hdr->params[0].fraction_bright_pixels.den = 1;
        hdr->params[0].color_saturation_mapping_flag = 1;
        hdr->params[0].color_saturation_weight = (AVRational){1, 1};
        size_t size;
        assert(av_dynamic_hdr_plus_to_t35(hdr, NULL, &size) == 0);
        uint8_t *data = av_malloc(size);
        assert(data);
        memset(data, 0xa5, size);
        assert(av_dynamic_hdr_plus_to_t35(hdr, &data, &size) == 0);
        assert(av_dynamic_hdr_plus_from_t35(parsed, data, size) == 0);
        assert(parsed->params[0].tone_mapping_flag == 0);
        assert(parsed->params[0].color_saturation_mapping_flag == 1);
        assert(av_cmp_q(parsed->params[0].color_saturation_weight, (AVRational){1, 1}) == 0);
        av_free(data);
        av_free(parsed);
        av_free(hdr);
    }
    return 0;
}
